package com.example.fdm

import java.io.RandomAccessFile
import java.net.HttpURLConnection
import java.net.URL

/**
 * يُنزّل جزءًا واحدًا من الملف (Range) ويكتبه مباشرة في موضعه الصحيح
 * داخل الملف النهائي بدون الحاجة لدمج ملفات مؤقتة لاحقًا.
 * يعيد true إذا اكتمل الجزء، و false إذا تم إيقافه (إيقاف مؤقت/إلغاء).
 */
class SegmentDownloader(
    private val url: String,
    private val raf: RandomAccessFile,
    private val fileLock: Any,
    private val segment: Segment,
    private val fileOffsetForSegmentStart: Long,
    private val onProgress: (bytes: Long) -> Unit,
    private val isActive: () -> Boolean
) {
    fun download(): Boolean {
        val rangeStart = segment.start + segment.downloaded
        val rangeEnd = segment.end
        if (rangeStart > rangeEnd) {
            segment.status = "done"
            return true
        }

        var conn: HttpURLConnection? = null
        try {
            conn = URL(url).openConnection() as HttpURLConnection
            conn.setRequestProperty("Range", "bytes=$rangeStart-$rangeEnd")
            conn.connectTimeout = 15000
            conn.readTimeout = 20000
            conn.connect()

            if (conn.responseCode != HttpURLConnection.HTTP_PARTIAL &&
                conn.responseCode != HttpURLConnection.HTTP_OK
            ) {
                return false
            }

            val input = conn.inputStream
            val buffer = ByteArray(16 * 1024)
            var filePos = fileOffsetForSegmentStart + segment.downloaded

            while (true) {
                if (!isActive()) {
                    input.close()
                    return false
                }
                val read = input.read(buffer)
                if (read == -1) break
                synchronized(fileLock) {
                    raf.seek(filePos)
                    raf.write(buffer, 0, read)
                }
                filePos += read
                segment.downloaded += read
                onProgress(read.toLong())
            }
            input.close()
            segment.status = "done"
            return true
        } catch (e: Exception) {
            return false
        } finally {
            conn?.disconnect()
        }
    }
}
