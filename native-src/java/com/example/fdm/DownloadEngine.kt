package com.example.fdm

import android.content.Context
import kotlinx.coroutines.*
import java.io.File
import java.io.RandomAccessFile
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLConnection
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

object DownloadEngine {

    lateinit var appContext: Context
    var listener: ((DownloadTask) -> Unit)? = null

    val tasks = ConcurrentHashMap<String, DownloadTask>()
    private val activeFlags = ConcurrentHashMap<String, AtomicBoolean>()
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // يُستدعى من الـ Plugin عندما يصبح هناك تنزيل نشط/لا يوجد، لتشغيل/إيقاف الـ Foreground Service
    var onActiveCountChanged: ((Int) -> Unit)? = null

    private fun activeCount() = tasks.values.count { it.status == "downloading" }

    fun addDownload(url: String, segmentsCount: Int): DownloadTask {
        val id = UUID.randomUUID().toString()
        val fileName = guessFileName(url)
        val dir = File(appContext.getExternalFilesDir(null), "Downloads")
        if (!dir.exists()) dir.mkdirs()
        val filePath = File(dir, fileName).absolutePath
        val task = DownloadTask(
            id = id, url = url, fileName = fileName, filePath = filePath,
            requestedSegments = segmentsCount.coerceIn(1, 32)
        )
        tasks[id] = task
        start(task)
        return task
    }

    fun pause(id: String) {
        activeFlags[id]?.set(false)
        tasks[id]?.let { it.status = "paused"; notify(it) }
    }

    fun resume(id: String) {
        val t = tasks[id] ?: return
        if (t.status == "paused" || t.status == "error") start(t)
    }

    fun cancel(id: String) {
        activeFlags[id]?.set(false)
        tasks.remove(id)?.let { runCatching { File(it.filePath).delete() } }
        onActiveCountChanged?.invoke(activeCount())
    }

    fun start(task: DownloadTask) {
        val flag = AtomicBoolean(true)
        activeFlags[task.id] = flag
        task.status = "downloading"
        task.speedBps = 0
        notify(task)
        onActiveCountChanged?.invoke(activeCount())

        scope.launch {
            try {
                if (task.totalBytes == 0L) probeAndPrepare(task)

                val raf = RandomAccessFile(File(task.filePath), "rw")
                val fileLock = Any()
                val lastTick = AtomicLong(System.currentTimeMillis())
                val bytesSinceTick = AtomicLong(0)

                val pending = task.segments.filter { it.status != "done" }
                val results = pending.map { seg ->
                    async(Dispatchers.IO) {
                        SegmentDownloader(
                            url = task.url,
                            raf = raf,
                            fileLock = fileLock,
                            segment = seg,
                            fileOffsetForSegmentStart = seg.start,
                            onProgress = { inc ->
                                task.downloadedBytes += inc
                                val sum = bytesSinceTick.addAndGet(inc)
                                val now = System.currentTimeMillis()
                                val elapsed = now - lastTick.get()
                                if (elapsed > 400) {
                                    task.speedBps = sum * 1000 / elapsed
                                    bytesSinceTick.set(0)
                                    lastTick.set(now)
                                    notify(task)
                                }
                            },
                            isActive = { flag.get() }
                        ).download()
                    }
                }.awaitAll()
                raf.close()

                when {
                    task.segments.all { it.status == "done" } -> {
                        task.status = "completed"
                        task.downloadedBytes = task.totalBytes
                        task.speedBps = 0
                    }
                    !flag.get() -> task.status = "paused"
                    else -> task.status = "error"
                }
            } catch (e: CancellationException) {
                task.status = "paused"
            } catch (e: Exception) {
                task.status = if (!flag.get()) "paused" else "error"
            }
            notify(task)
            onActiveCountChanged?.invoke(activeCount())
        }
    }

    /** يفحص الخادم: هل يدعم الاستئناف الجزئي (Range)، وحجم الملف الكلي، ثم يجهّز الأجزاء والملف على القرص */
    private fun probeAndPrepare(task: DownloadTask) {
        val conn = URL(task.url).openConnection() as HttpURLConnection
        conn.setRequestProperty("Range", "bytes=0-0")
        conn.connectTimeout = 15000
        conn.connect()
        val supportsRange = conn.responseCode == 206
        val total = if (supportsRange) {
            val cr = conn.getHeaderField("Content-Range") // "bytes 0-0/12345"
            cr?.substringAfter("/")?.toLongOrNull() ?: conn.contentLengthLong
        } else {
            conn.contentLengthLong
        }
        conn.disconnect()

        task.totalBytes = if (total > 0) total else 0
        val segCount = if (supportsRange && task.totalBytes > 0) task.requestedSegments else 1

        File(task.filePath).parentFile?.mkdirs()
        RandomAccessFile(File(task.filePath), "rw").use {
            if (task.totalBytes > 0) it.setLength(task.totalBytes)
        }

        if (task.segments.isEmpty()) {
            if (task.totalBytes <= 0) {
                // حجم غير معروف من الخادم: جزء واحد فقط بلا حدود Range دقيقة
                task.segments.add(Segment(0, 0, Long.MAX_VALUE))
            } else {
                val size = task.totalBytes / segCount
                for (i in 0 until segCount) {
                    val start = i * size
                    val end = if (i == segCount - 1) task.totalBytes - 1 else start + size - 1
                    task.segments.add(Segment(i, start, end))
                }
            }
        }
    }

    private fun guessFileName(url: String): String {
        val clean = url.substringBefore("?").substringBefore("#")
        val name = clean.substringAfterLast("/").ifBlank { "download-${System.currentTimeMillis()}" }
        return name
    }

    private fun notify(task: DownloadTask) {
        listener?.invoke(task)
    }
}
