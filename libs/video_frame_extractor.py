import os
import cv2
from PyQt5.QtCore import QThread, pyqtSignal

class VideoFrameExtractor(QThread):
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(str, int)  # video_path, frame_count

    def __init__(self, video_path, output_dir, frames_per_sec=10, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.output_dir = output_dir
        self.frames_per_sec = frames_per_sec
        self._is_running = True

    def run(self):
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self.finished.emit(self.video_path, 0)
            return
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        frame_interval = int(fps / self.frames_per_sec) if self.frames_per_sec < fps else 1
        count = 0
        saved = 0
        basename = os.path.splitext(os.path.basename(self.video_path))[0]
        os.makedirs(self.output_dir, exist_ok=True)
        while cap.isOpened() and self._is_running:
            ret, frame = cap.read()
            if not ret:
                break
            if count % frame_interval == 0:
                frame_name = f"{basename}_frame_{count:06d}.jpg"
                cv2.imwrite(os.path.join(self.output_dir, frame_name), frame)
                saved += 1
                self.progress.emit(count, total_frames)
            count += 1
        cap.release()
        self.finished.emit(self.video_path, saved)

    def stop(self):
        self._is_running = False
