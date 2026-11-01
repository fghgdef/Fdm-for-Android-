package com.example.fdm

data class Segment(
    val index: Int,
    val start: Long,
    val end: Long,
    @Volatile var downloaded: Long = 0,
    @Volatile var status: String = "pending" // pending, done
)

data class DownloadTask(
    val id: String,
    val url: String,
    var fileName: String,
    var filePath: String,
    var totalBytes: Long = 0,
    @Volatile var downloadedBytes: Long = 0,
    @Volatile var status: String = "queued", // queued, downloading, paused, completed, error
    @Volatile var speedBps: Long = 0,
    var requestedSegments: Int = 4,
    val segments: MutableList<Segment> = mutableListOf()
)
