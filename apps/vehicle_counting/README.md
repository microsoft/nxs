# VEHICLE COUNTING APP

This application analyzes a video stream, detects vehicles, tracks them and reports a count of each vehicle type periodically.

![](data/sample.png)

## ***APIs***

### *Submit video: [POST] /video*

Parameters:
- [required] videoURL: direct url to a video
- [required] regions: a list of region to track vehicles
    - roi: list of points in clock-wise order. Points must be in relative coordinates. (green region in the image below)
    - line: count vehicle whenever it crosses this line. (red line in the image below)
- [optional] trackingClasses: a list of class to track including car, bus, truck, motobike.
- [optional] count_interval_secs: time interval in seconds to store counting results into DB.
- [optional] debug: enable/disable debug mode. If set to true, the app generates visualized frame every second for debugging purposes.

Return:
- videoUuid: id used for querying results.

![My image](data/readme_1.jpeg)

Example: Counting cars and trucks passing the red line in the green region.
```
{
  "videoUrl": "",
  "regions": [
    {
      "roi": {
        "points": [
          {
            "x": 0.134722222,
            "y": 0.947916667
          },
          {
            "x": 0.270833333,
            "y": 0.695833333
          },
          {
            "x": 0.479166667,
            "y": 0.677083333
          },
          {
            "x": 0.618055556,
            "y": 0.90625
          }
        ]
      },
      "line": {
        "p0": {
          "x": 0.227777778,
          "y": 0.783333333
        },
        "p1": {
          "x": 0.540277778,
          "y": 0.783333333
        }
      }
    }
  ],
  "trackingClasses": [
    "car",
    "truck"
  ],
  "countIntervalSecs": 900,
  "debug": false
}
```

Output example:
```
{
  "videoUuid": "2df258930579444096d82f0b4c69dbec"
}
```

### *Get counting outputs: [GET] /video/counts*
Parameters:
- [required] videoUuid: id returned in [POST] /video
- [optional] last_ts: timestamp. If set to 0, return the latest counts. Otherwise, return the all the counts after last_ts timestamp.

Return: List of counts per region per existing timestamp.

Output example:
```
[
  {
    "timestamp": 299,
    "counts": [
      {
        "roiIdx": 0,
        "counts": [
          {
            "className": "car",
            "count": 33
          },
          {
            "className": "motorcycle",
            "count": 0
          },
          {
            "className": "bus",
            "count": 1
          },
          {
            "className": "truck",
            "count": 3
          }
        ]
      }
    ]
  }
]
```

### *Get debugging frames: [GET] /video/visualizations*
Parameters:
- [required] videoUuid: id returned in [POST] /video
- [optional] timestamp_secs : timestamp

Return: List of frames near the input timestamp

Output example:
```
{
  "fromTs": 10.9, # starting timestamp of this segment
  "toTs": 19.9, # ending timestamp of this segment
  "visualizedFrames": [
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_0.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D",
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_1.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D",
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_2.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D",
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_3.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D",
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_4.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D",
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_5.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D",
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_6.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D",
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_7.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D",
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_8.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D",
    "https://teststorage.blob.core.windows.net/sdot/sdot_logs/2df258930579444096d82f0b4c69dbec_1_9.jpg?se=2022-01-13T21%3A26%3A09Z&sp=r&sv=2020-06-12&ss=b&srt=co&sig=n8Aex2PaMNwfraDJzX3oaoYuGAInz69zqeAhyrWXDMo%3D"
  ]
}
```

### *Get list of videos: [GET] /video*
Parameters:
- [required] status: status of video to query [PENDING, RUNNING, FAILED, STOPPED, COMPLETED]

Return: list of video ids with queried status.

### *Terminate task: [POST] /video/terminate*

NOTE: Due to resource contraint of the current staging server, only 2-3 videos can be processed in parallel. You can use this API to terminate RUNNING/PENDING tasks to make room for other tasks to run.

Parameters:
- [required] videoUuid: id returned in [POST] /video

Return: None

## Deployment
Check [DEPLOY](DEPLOY.md).