package com.example.fdm

import android.content.Intent
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin

@CapacitorPlugin(name = "DownloadManager")
class DownloadManagerPlugin : Plugin() {

    override fun load() {
        DownloadEngine.appContext = context.applicationContext
        DownloadEngine.listener = { task ->
            notifyListeners("downloadProgress", taskToJS(task))
        }
        DownloadEngine.onActiveCountChanged = { count ->
            val svcIntent = Intent(context, DownloadForegroundService::class.java)
            if (count > 0) {
                svcIntent.action = DownloadForegroundService.ACTION_START
                context.startForegroundService(svcIntent)
            } else {
                svcIntent.action = DownloadForegroundService.ACTION_STOP
                context.startService(svcIntent)
            }
        }
    }

    @PluginMethod
    fun addDownload(call: PluginCall) {
        val url = call.getString("url")
        if (url.isNullOrBlank()) {
            call.reject("الرابط مطلوب")
            return
        }
        val segments = call.getInt("segments") ?: 4
        val task = DownloadEngine.addDownload(url, segments)
        call.resolve(taskToJS(task))
    }

    @PluginMethod
    fun pause(call: PluginCall) {
        val id = call.getString("id") ?: return call.reject("id مطلوب")
        DownloadEngine.pause(id)
        call.resolve()
    }

    @PluginMethod
    fun resume(call: PluginCall) {
        val id = call.getString("id") ?: return call.reject("id مطلوب")
        DownloadEngine.resume(id)
        call.resolve()
    }

    @PluginMethod
    fun cancel(call: PluginCall) {
        val id = call.getString("id") ?: return call.reject("id مطلوب")
        DownloadEngine.cancel(id)
        call.resolve()
    }

    @PluginMethod
    fun list(call: PluginCall) {
        val arr = JSArray()
        DownloadEngine.tasks.values.forEach { arr.put(taskToJS(it)) }
        val ret = JSObject()
        ret.put("items", arr)
        call.resolve(ret)
    }

    private fun taskToJS(t: DownloadTask): JSObject {
        val o = JSObject()
        o.put("id", t.id)
        o.put("url", t.url)
        o.put("fileName", t.fileName)
        o.put("totalBytes", t.totalBytes)
        o.put("downloadedBytes", t.downloadedBytes)
        o.put("status", t.status)
        o.put("speedBps", t.speedBps)
        return o
    }
}
