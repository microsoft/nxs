import copy
import json
import os
import threading
import time
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import cv2
import numpy as np
from apps.vehicle_counting.app_types.app_request import (
    InDbTrackingAppRequest,
    RequestStatus,
)
from apps.vehicle_counting.worker.utils import *
from nxs_libs.db import NxsDbFactory, NxsDbType
from nxs_libs.storage import NxsStorageFactory, NxsStorageType
from nxs_types.infer import NxsInferInput, NxsInferInputType, NxsTensorsInferRequest
from nxs_types.infer_result import (
    NxsInferDetectorBBoxLocation,
    NxsInferDetectorResult,
    NxsInferResult,
)
from shapely.geometry import Point, Polygon

DB_TASKS_COLLECTION_NAME = "tasks"
DB_COUNTS_COLLECTION_NAME = "counts"
DB_LOGS_COLLECTION_NAME = "logs"
STORAGE_LOGS_DIR_PATH = "logs"


class OfflineVehicleTrackingApp:
    DATA_DIR = "/data"

    def __init__(
        self,
        video_uuid: str,
        frame_width: int,
        frame_height: int,
        frame_rate: int,
        nxs_infer_url: str,
        nxs_api_key: str,
        detector_uuid: str,
        tracker_uuid: str,
        video_url: str,
        rois: List[NxsRoi],
        lines: List[NxsLine],
        tracking_classes: List[str] = ["car", "motorcycle", "bus", "truck"],
        treat_all_classes_as_one: bool = False,
        detector_min_score: float = 0.4,
        detector_interval_secs: float = 1,
        duplicate_iou_thresh: float = 0.65,
        merge_iou_thresh: float = 0.5,
        object_expiration_secs: float = 2,
        tracking_score_thresh: float = 0.975,
        skip_frame: int = 2,
        collect_logs: bool = False,
        blobstore_conn_str: str = "",
        blobstore_container_name: str = "",
        cosmosdb_conn_str: str = "",
        cosmosdb_db_name: str = "",
        counting_report_interval_secs: int = 30,
        visualize: bool = False,
        job_duration: int = 21600,
    ) -> None:
        self.video_uuid = video_uuid
        self.nxs_infer_url = nxs_infer_url
        self.nxs_api_key = nxs_api_key
        self.detector_uuid = detector_uuid
        self.tracker_uuid = tracker_uuid
        self.name = "VEHICLE_TRACKING_APP"

        self.video_url = video_url
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.frame_rate = frame_rate

        self.job_duration = job_duration

        # self.cap = cv2.VideoCapture(video_url)
        # self.frame_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        # self.frame_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        # self.frame_rate = int(round(self.cap.get(cv2.CAP_PROP_FPS)))

        self.rois = rois
        self.lines = lines
        self.tracking_classes = tracking_classes
        self.treat_all_classes_as_one = treat_all_classes_as_one
        self.detector_min_score = detector_min_score
        self.detector_interval_secs = detector_interval_secs
        self.duplicate_iou_thresh = duplicate_iou_thresh
        self.merge_iou_thresh = merge_iou_thresh
        self.object_expiration_secs = object_expiration_secs
        self.tracking_score_thresh = tracking_score_thresh

        self.total_extracted_frames: int = 0
        self.total_processed_frames: int = 0
        self.skip_frame = skip_frame

        self.visualize = visualize
        self.collect_logs = collect_logs
        self.blobstore_conn_str = blobstore_conn_str
        self.blobstore_container_name = blobstore_container_name
        self.cosmosdb_conn_str = cosmosdb_conn_str
        self.cosmosdb_db_name = cosmosdb_db_name
        self.logs = []
        self.log_id = 0

        self.counting_report_interval_secs = counting_report_interval_secs

        self.NUM_FRAMES_PER_SEC = int(self.frame_rate / (1 + self.skip_frame))
        self.WINDOW_LENGTH = int(self.frame_rate * self.detector_interval_secs)

        self.STOP_FLAG = False

        self.track_dict: Dict[int, NxsTrack] = {}
        self.track_count = 0

        self.class_count_dicts: List[Dict[str, int]] = [{} for _ in lines]
        for class_name in self.tracking_classes:
            for class_count_dict in self.class_count_dicts:
                class_count_dict[class_name] = 0

        if not os.path.exists(self.DATA_DIR):
            os.makedirs(self.DATA_DIR)

        self.job_completed = False
        self.video_ended = False
        self.video_frames = []
        self.video_frame_timestamps = []

        # create a log file
        self.LOG_FILE = f"{video_uuid}.txt"
        with open(self.LOG_FILE, "w") as f:
            pass

        self.starting_utc_time = datetime.now(timezone.utc)
        self.starting_utc_ts = datetime.now(timezone.utc).timestamp()

        self.downloaded_videos: List[Tuple[int, str]] = []

        self.to_exit_threads = False

        self.download_thr = threading.Thread(target=self.download_video_thread, args=())
        self.download_thr.start()

        self.decode_thr = threading.Thread(target=self.decode_video_thread, args=())
        self.decode_thr.start()

    def _append_log(self, data):
        current_time = datetime.utcnow().strftime("%D:%H:%M:%S")
        print("{} - {}".format(current_time, data))
        with open(self.LOG_FILE, "a") as f:
            f.write("{} - {}".format(current_time, data))
            f.write("\n")

    def run_tracking(self):
        def process_frames(obj_id: int, frames: List[np.ndarray]):
            obj_track = self.track_dict[obj_id]

            for frame_idx in range(1, len(frames)):
                frame = frames[frame_idx]

                infer_res = run_tracker(
                    self.nxs_infer_url,
                    self.tracker_uuid,
                    obj_track.templates[-1],
                    frame,
                    obj_track.track[-1],
                    self.nxs_api_key,
                    logging_fn=self._append_log,
                )

                obj_track.track.append(infer_res.detections[0].bbox)
                obj_track.track_scores.append(infer_res.detections[0].score)
                if infer_res.detections[0].score < self.tracking_score_thresh:
                    obj_track.is_active = False

        last_ts = -1
        last_frame_ts = -1

        miss_deadline = 0
        hit_deadline = 0

        avg_lat = 0
        count = 0

        self._update_log_file()
        last_updated_log_ts = time.time()

        while not self.STOP_FLAG:
            t0 = time.time()
            frames, frames_timestamps, is_end_of_video = self.get_batch(
                self.WINDOW_LENGTH
            )

            if last_frame_ts >= self.job_duration * 1000:
                self.job_completed = True
                self.report_counting(last_frame_ts)
                self.to_exit_threads = True
                break

            if is_end_of_video or self.job_completed:
                # we don't really need to track the last-window
                if last_frame_ts > 0:
                    self.report_counting(last_frame_ts)
                self.to_exit_threads = True
                break

            if len(frames_timestamps) == 0:
                time.sleep(0.1)
                continue

            if frames_timestamps[-1] > 0:
                last_frame_ts = frames_timestamps[-1]
            else:
                for idx in range(len(frames_timestamps) - 1, -1, -1):
                    if frames_timestamps[idx] > 0:
                        last_frame_ts = frames_timestamps[idx]

            self.remove_inactive_tracks()
            self.remove_out_of_rois_tracks()
            self.remove_expired_objects()

            dets = run_detector(
                self.nxs_infer_url,
                self.detector_uuid,
                frames[0],
                self.nxs_api_key,
                logging_fn=self._append_log,
            ).detections
            self.process_detections(frames[0], dets)

            tracking_args = []
            for obj_id in self.track_dict:
                tracking_args.append((obj_id, frames))

            if len(tracking_args) > 0:
                executor = ThreadPoolExecutor(max_workers=min(16, len(tracking_args)))
                results = []
                for args in tracking_args:
                    f = executor.submit(process_frames, *args)
                    results.append(f)
                executor.shutdown(wait=True)

                for r in results:
                    _ = r.result()

            # count objects
            for frame_idx in range(len(frames)):
                if self.visualize:
                    vis_frame = np.array(frames[frame_idx])

                if self.collect_logs and frame_idx == len(frames) - 1:
                    log_frame = np.array(frames[frame_idx])

                for obj_id in self.track_dict:
                    obj_track = self.track_dict[obj_id]

                    bboxes = obj_track.track[
                        : len(obj_track.track) - len(frames) + frame_idx + 1
                    ]
                    scores = obj_track.track_scores[
                        : len(obj_track.track) - len(frames) + frame_idx + 1
                    ]

                    if not obj_track.is_counted:
                        if self.is_passing_line(bboxes, self.lines[obj_track.roi_idx]):
                            obj_track.is_counted = True
                            self.class_count_dicts[obj_track.roi_idx][
                                obj_track.class_name
                            ] += 1
                            break

                    if self.visualize:
                        vis_frame = self.draw_obj(
                            vis_frame, obj_id, bboxes[-1], scores[-1]
                        )

                    if self.collect_logs and frame_idx == len(frames) - 1:
                        log_frame = self.draw_obj(
                            log_frame, obj_id, bboxes[-1], scores[-1]
                        )

                if self.visualize:
                    vis_frame = self.draw_rois(vis_frame)
                    vis_frame = self.draw_lines(vis_frame)
                    vis_frame = self.draw_frame_number(
                        vis_frame, self.total_processed_frames + frame_idx
                    )
                    self.visualize_frame(vis_frame)

                if self.collect_logs and frame_idx == len(frames) - 1:
                    log_frame = self.draw_rois(log_frame)
                    log_frame = self.draw_lines(log_frame)
                    log_frame = self.draw_frame_number(
                        log_frame, self.total_processed_frames + frame_idx
                    )

            self.total_processed_frames += len(frames)

            if last_ts < 0:
                last_ts = frames_timestamps[0]
            else:
                if (
                    frames_timestamps[-1] - last_ts
                    >= self.counting_report_interval_secs * 1000
                ):
                    self.report_counting(frames_timestamps[-1])
                    last_ts = frames_timestamps[-1]

            if self.collect_logs:
                self.snapshot_stats(log_frame, frames_timestamps[-1])

                if len(self.logs) >= 10:
                    # print("uploading logs")
                    self.upload_logs()
                    # print("finished uploading logs")

            lat = time.time() - t0

            avg_lat = (avg_lat * count + lat) / (count + 1)
            count += 1

            if lat > 1:
                miss_deadline += 1
            else:
                hit_deadline += 1

            miss_rate = float(miss_deadline) / (miss_deadline + hit_deadline)

            if count % 300 != 1:
                continue

            # print(f"Total processed frames: {self.total_processed_frames}")
            # print(f"Total objects this round: {len(self.track_dict)}")
            # print(f"Latency this round: {lat} secs")
            # print(f"Avg latency: {avg_lat} secs")
            # print(f"Miss rate: {miss_rate}")
            # print(self.class_count_dicts)
            # print("")

            self._append_log(f"Total processed frames: {self.total_processed_frames}")
            self._append_log(f"Latency this round: {lat} secs")
            self._append_log(f"Avg latency: {avg_lat} secs")
            self._append_log(f"Counts: {self.class_count_dicts}")
            self._append_log("")

            if time.time() - last_updated_log_ts > 1800:
                self._update_log_file()
                last_updated_log_ts = time.time()

    def _update_log_file(self):
        storage_client = NxsStorageFactory.create_storage(
            NxsStorageType.AzureBlobstorage,
            connection_str=self.blobstore_conn_str,
            container_name=self.blobstore_container_name,
        )

        storage_client.upload(self.LOG_FILE, STORAGE_LOGS_DIR_PATH, True)

    def report_counting(self, ts):
        cosmosdb_client = NxsDbFactory.create_db(
            NxsDbType.MONGODB,
            uri=self.cosmosdb_conn_str,
            db_name=self.cosmosdb_db_name,
        )

        completed_percent = min(1.0, ts / (self.job_duration * 1000)) * 100

        ending_ts = self.starting_utc_ts + ts / 1000

        data = {
            "zone": "global",
            "video_uuid": self.video_uuid,
            "timestamp": ts,
            "counts": copy.deepcopy(self.class_count_dicts),
            "completed_percent": completed_percent,
            "starting_utc_time": str(self.starting_utc_time),
            "starting_utc_ts": self.starting_utc_ts,
            "ending_utc_time": str(datetime.utcfromtimestamp(ending_ts)),
            "ending_utc_ts": ending_ts,
        }

        cosmosdb_client.insert(
            DB_COUNTS_COLLECTION_NAME,
            data,
        )

    def snapshot_stats(self, frame, frame_ts):
        track_snapshots = []

        for obj_id in self.track_dict:
            track = self.track_dict[obj_id]
            if track.is_active:
                bbox = track.track[-1]
                cloned_track = {
                    "id": track.id,
                    "class_name": track.class_name,
                    "is_counted": track.is_counted,
                    "bbox": [bbox.left, bbox.top, bbox.right, bbox.bottom],
                    "score": track.track_scores[-1],
                }
                track_snapshots.append(cloned_track)

        self.logs.append(
            (
                frame,
                frame_ts,
                copy.deepcopy(self.class_count_dicts),
                track_snapshots,
            )
        )

    def upload_logs(self):
        storage_client = NxsStorageFactory.create_storage(
            NxsStorageType.AzureBlobstorage,
            connection_str=self.blobstore_conn_str,
            container_name=self.blobstore_container_name,
        )
        cosmosdb_client = NxsDbFactory.create_db(
            NxsDbType.MONGODB,
            uri=self.cosmosdb_conn_str,
            db_name=self.cosmosdb_db_name,
        )

        cosmosdb_client.insert(
            DB_LOGS_COLLECTION_NAME,
            {
                "zone": "global",
                "video_uuid": self.video_uuid,
                "log_id": self.log_id,
                "start_ts": self.logs[0][1],
                "end_ts": self.logs[-1][1],
                "num_logs": len(self.logs),
            },
        )

        logs = []

        for log_idx, log in enumerate(self.logs):
            frame, frame_idx, counts, snapshots = log
            frame_file_name = f"{self.video_uuid}_{self.log_id}_{log_idx}.jpg"
            cv2.imwrite(frame_file_name, frame)
            storage_client.upload(frame_file_name, STORAGE_LOGS_DIR_PATH, True)
            os.remove(frame_file_name)

            logs.append({"counts": counts, "snapshots": snapshots})

        tmp_log_path = f"{self.video_uuid}_{self.log_id}.txt"
        json.dump(logs, open(tmp_log_path, "w"))
        storage_client.upload(tmp_log_path, STORAGE_LOGS_DIR_PATH, True)
        os.remove(tmp_log_path)

        self.logs.clear()
        self.log_id += 1

    def get_free_idx(self) -> int:
        self.track_count += 1
        return self.track_count

    def get_chunk_names(self, num_retries: int = 60):
        base_url = self.video_url[: self.video_url.rindex("/")]

        chunk_names = []

        chunklist_path = ""
        for retry in range(num_retries):
            try:
                data = requests.get(self.video_url).content.decode("utf-8")
                lines = data.split("\n")

                for line in lines:
                    if ".m3u8" in line:
                        chunklist_path = f"{base_url}/{line}"
                    if ".ts" in line:
                        chunk_names.append(line)

                if chunk_names or chunklist_path != "":
                    break
                else:
                    time.sleep(5)
            except Exception as e:
                self._append_log(str(e))
                time.sleep(5)
                if retry == num_retries - 1:
                    self.video_ended = True

        if chunk_names:
            return chunk_names

        for retry in range(num_retries):
            try:
                data = requests.get(chunklist_path).content.decode("utf-8")
                lines = data.split("\n")

                for line in lines:
                    if ".ts" in line:
                        chunk_names.append(line)

                break
            except Exception as e:
                self._append_log(str(e))
                time.sleep(5)
                if retry == num_retries - 1:
                    self.video_ended = True

        return chunk_names

    def download_video_thread(self):
        self._append_log("Download thread is started...")

        base_url = self.video_url[: self.video_url.rindex("/")]
        last_downloaded = []

        starting_ts = time.time()

        idx = 0

        while (
            not self.video_ended and not self.job_completed and not self.to_exit_threads
        ):
            if time.time() - starting_ts > 1.1 * self.job_duration:
                self.video_ended = True
                break

            chunk_names = self.get_chunk_names()

            if self.video_ended:
                break

            # download chunks into files
            # chunk_names.sort()

            for chunk_name in chunk_names:
                if chunk_name in last_downloaded:
                    continue

                # print(f"Downloading chunk {chunk_name}\n")

                chunk_idx = int(chunk_name.replace(".ts", "").split("_")[-1])
                chunk_url = f"{base_url}/{chunk_name}"

                for _ in range(5):
                    try:
                        data = requests.get(chunk_url, allow_redirects=True).content
                        chunk_path = f"{self.DATA_DIR}/chunk_{idx}"
                        open(chunk_path, "wb").write(data)
                        self.downloaded_videos.append((chunk_idx, chunk_path))
                        break
                    except Exception as e:
                        self._append_log(str(e))
                        time.sleep(1)

                if len(last_downloaded) > 10:
                    last_downloaded.pop(0)

                if chunk_name not in last_downloaded:
                    last_downloaded.append(chunk_name)

                idx += 1

            time.sleep(3)

        self._append_log("Download thread is stopped...")

    def decode_video_thread(self):
        self._append_log("Decode thread is started...")

        last_chunk_idx = -1
        frame_idx = 0
        self.starting_utc_time = datetime.now(timezone.utc)
        self.starting_utc_ts = self.starting_utc_time.timestamp()
        video_ts = 0
        chunk_lens = []  # in secs
        while not self.to_exit_threads:
            if video_ts >= self.job_duration * 1000:
                self.job_completed = True
                break

            if not self.downloaded_videos and self.video_ended:
                # could not get any more frames
                break

            if not self.downloaded_videos:
                time.sleep(1)
                continue

            if len(self.video_frames) > 5 * self.NUM_FRAMES_PER_SEC:
                time.sleep(1)
                continue

            chunk_idx, chunk_path = self.downloaded_videos.pop(0)

            # print(f"Decoding chunk {chunk_path}\n")

            if last_chunk_idx > 0 and chunk_idx < last_chunk_idx:
                delta = chunk_idx - last_chunk_idx - 1
                if delta > 0:
                    # some chunks are missing
                    video_ts += delta * np.mean(chunk_lens) * 1000

            cap = cv2.VideoCapture(chunk_path)

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps == 0:
                fps = self.frame_rate
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            chunk_len = frame_count / fps
            chunk_lens.append(chunk_len)
            frame_time = (1.0 / fps) * 1000

            while True:
                _, img = cap.read()  # BGR
                if isinstance(img, type(None)):
                    break

                video_ts += frame_time
                if frame_idx % (self.skip_frame + 1) == 0:
                    self.video_frame_timestamps.append(video_ts)
                    self.video_frames.append(img)

                frame_idx += 1
                self.total_extracted_frames += 1

            cap.release()

            try:
                os.remove(chunk_path)
            except:
                pass

            last_chunk_idx = chunk_idx

        self._append_log("Decode thread is stopped...")

    """
    def get_batch(self, batch_size):
        images = []
        timestamps = []
        is_end_of_video = False
        for _ in range(batch_size):
            _, img = self.cap.read()  # BGR
            if not isinstance(img, type(None)):
                if self.total_extracted_frames % (self.skip_frame + 1) == 0:
                    timestamps.append(self.cap.get(cv2.CAP_PROP_POS_MSEC))
                    images.append(img)
            else:
                is_end_of_video = True
                break

            self.total_extracted_frames += 1

        return images, timestamps, is_end_of_video
    """

    def get_batch(self, batch_size):
        images = []
        timestamps = []
        is_end_of_video = False

        batch_size = int(float(batch_size) / (1 + self.skip_frame))

        if len(self.video_frames) >= batch_size:
            for _ in range(batch_size):
                timestamps.append(self.video_frame_timestamps.pop(0))
                images.append(self.video_frames.pop(0))
        elif len(self.video_frames) < batch_size and self.video_ended:
            for _ in range(len(self.video_frames)):
                timestamps.append(self.video_frame_timestamps.pop(0))
                images.append(self.video_frames.pop(0))
            is_end_of_video = True
        else:
            is_end_of_video = self.video_ended

        return images, timestamps, is_end_of_video

    def is_passing_line(
        self, bboxes: List[NxsInferDetectorBBoxLocation], line: NxsLine
    ):
        if len(bboxes) < 6:
            return False

        vs = []
        for bbox in bboxes:
            center_x = (bbox.left + bbox.right) // 2
            center_y = (bbox.top + bbox.bottom) // 2
            v1 = [line.p0.x - center_x, line.p0.y - center_y]
            v2 = [line.p1.x - center_x, line.p1.y - center_y]
            v = [v1[0] + v2[0], v1[1] + v2[1]]
            vs.append(v)

        for i in range(3):
            v1 = vs[i]
            v2 = vs[-i - 1]

            if v1[0] * v1[1] * v2[0] * v2[1] > 0:
                return False

        return True

    def remove_inactive_tracks(self):
        inactive_track_ids = []
        for obj_id in self.track_dict:
            track = self.track_dict[obj_id]
            if not track.is_active:
                inactive_track_ids.append(obj_id)

        for obj_id in inactive_track_ids:
            self.track_dict.pop(obj_id, None)

    def remove_out_of_rois_tracks(self):
        out_of_rois_obj_ids = []
        for obj_id in self.track_dict:
            track = self.track_dict[obj_id]

            last_bbox = track.track[-1]

            roi = Polygon(self.rois[track.roi_idx].to_ndarray())
            if not (
                Point(last_bbox.left, last_bbox.top).within(roi)
                or Point(last_bbox.right, last_bbox.top).within(roi)
                or Point(last_bbox.left, last_bbox.bottom).within(roi)
                or Point(last_bbox.right, last_bbox.bottom).within(roi)
            ):
                out_of_rois_obj_ids.append(obj_id)

        for obj_id in out_of_rois_obj_ids:
            self.track_dict.pop(obj_id, None)
            # print("remove_out_of_rois_tracks", f"removed obj {obj_id}")

    def remove_expired_objects(self):
        expired_ids = []
        for obj_id in self.track_dict:
            track = self.track_dict[obj_id]
            if (
                self.total_processed_frames - track.last_frame_idx
                > self.NUM_FRAMES_PER_SEC * self.object_expiration_secs
            ):
                expired_ids.append(obj_id)

        for obj_id in expired_ids:
            self.track_dict.pop(obj_id, None)

    def process_detections(self, frame: np.ndarray, dets: List[NxsInferDetectorResult]):
        duplicate_obj_ids = []

        for det in dets:
            if det.class_name not in self.tracking_classes:
                continue

            if det.score < self.detector_min_score:
                continue

            within_rois = False
            for roi_idx, roi in enumerate(self.rois):
                if self.is_in_roi(det.bbox, roi):
                    within_rois = True
                    break
            if not within_rois:
                continue

            # match this detection with tracking objects
            (
                best_obj_id,
                best_iou,
                matched_obj_ids,
            ) = self.find_matched_objects(det)

            for obj_idx in matched_obj_ids:
                if obj_idx != best_obj_id:
                    duplicate_obj_ids.append(obj_idx)

            # update best matched obj
            if best_iou > self.merge_iou_thresh:
                matched_track = self.track_dict[best_obj_id]
                matched_track.dets.append(det)
                matched_track.track.append(det.bbox)
                matched_track.track_scores.append(det.score)
                matched_track.last_frame_idx = self.total_processed_frames
                continue

            new_obj_id = self.get_free_idx()

            template = preprocess_examplar(
                frame,
                [
                    det.bbox.left,
                    det.bbox.top,
                    det.bbox.right,
                    det.bbox.bottom,
                ],
            )

            self.track_dict[new_obj_id] = NxsTrack(
                id=new_obj_id,
                class_name=det.class_name,
                is_active=True,
                is_counted=False,
                start_frame_idx=self.total_processed_frames,
                last_frame_idx=self.total_processed_frames,
                templates=[template],
                dets=[det],
                track=[det.bbox],
                track_scores=[det.score],
                roi_idx=roi_idx,
            )

        # remove duplicate objects
        for obj_idx in duplicate_obj_ids:
            self.track_dict.pop(obj_idx, None)

    def find_matched_objects(
        self, det: NxsInferDetectorResult
    ) -> Tuple[int, float, List[int]]:
        best_matched_obj_id = 0
        best_iou = 0
        matched_obj_ids: List[int] = []
        for obj_id in self.track_dict:
            track = self.track_dict[obj_id]

            if track.start_frame_idx == self.total_processed_frames:
                # ignore just-added track
                continue

            # prev_det = track.dets[-1]

            if not self.treat_all_classes_as_one and det.class_name != track.class_name:
                continue

            iou = compute_iou(det.bbox, track.track[-1])

            if iou > best_iou:
                best_iou = iou
                best_matched_obj_id = obj_id

            if iou > self.duplicate_iou_thresh:
                matched_obj_ids.append(obj_id)

        return best_matched_obj_id, best_iou, matched_obj_ids

    def is_in_roi(self, det: NxsInferDetectorBBoxLocation, roi: NxsRoi):
        center_x = int((det.left + det.right) / 2)
        center_y1 = int(0.75 * det.top + 0.25 * det.bottom)
        center_y2 = int(0.25 * det.top + 0.75 * det.bottom)

        p1 = Point(center_x, center_y1)
        p2 = Point(center_x, center_y2)

        roi = Polygon(roi.to_ndarray())

        if p1.within(roi) or p2.within(roi):
            return True

        return False

    def draw_obj(
        self,
        frame,
        obj_id: int,
        bbox: NxsInferDetectorBBoxLocation,
        score: float,
        color=(0, 0, 255),
        thickness=1,
    ):
        frame = cv2.rectangle(
            frame,
            (bbox.left, bbox.top),
            (bbox.right, bbox.bottom),
            color,
            thickness=thickness,
            lineType=cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"{obj_id}",
            (bbox.left, bbox.top - 3),
            0,
            1,
            [0, 255, 0],
            thickness=1,
            lineType=cv2.LINE_AA,
        )
        return frame

    def draw_frame_number(self, frame, frame_idx: int):
        return cv2.putText(
            frame,
            f"{frame_idx}",
            (50, 50),
            0,
            1,
            [0, 0, 255],
            thickness=1,
            lineType=cv2.LINE_AA,
        )

    def draw_det(
        self,
        frame,
        det: NxsInferDetectorResult,
        color=(0, 0, 255),
        thickness=1,
    ):
        return cv2.rectangle(
            frame,
            (det.bbox.left, det.bbox.top),
            (det.bbox.right, det.bbox.bottom),
            color,
            thickness=thickness,
            lineType=cv2.LINE_AA,
        )

    def draw_rois(self, frame):
        for roi in self.rois:
            frame = self.draw_roi(frame, roi)
        return frame

    def draw_roi(self, frame, roi: NxsRoi):
        if not roi:
            return frame

        cv2.polylines(
            frame,
            np.array([[roi.to_ndarray()]], dtype=np.int32),
            True,
            (0, 255, 0),
            thickness=3,
        )
        return frame

    def draw_lines(self, frame):
        for line_idx, line in enumerate(self.lines):
            label = ""
            for class_name in self.class_count_dicts[line_idx]:
                label += str(self.class_count_dicts[line_idx][class_name]) + " "
            cv2.putText(
                frame,
                label,
                (line.p0.x, line.p0.y),
                0,
                1,
                [225, 255, 255],
                thickness=1,
                lineType=cv2.LINE_AA,
            )
            frame = self.draw_line(frame, line)
        return frame

    def draw_line(self, frame, line: NxsLine, color=(0, 0, 255), thickness=1):
        if not line:
            return frame

        frame = cv2.line(
            frame,
            (line.p0.x, line.p0.y),
            (line.p1.x, line.p1.y),
            color,
            thickness,
        )
        return frame

    def visualize_frame(self, frame):
        while True:
            cv2.imshow(self.name, frame)

            key = cv2.waitKey(1)
            if key & 0xFF == ord("q"):
                self.STOP_FLAG = True
                break
            if key & 0xFF == ord("c"):
                break

        # cv2.imshow(self.name, frame)

        # key = cv2.waitKey(1)
        # if key & 0xFF == ord("q"):
        #     self.STOP_FLAG = True
