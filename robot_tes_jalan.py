import serial
import time
import cv2
import numpy as np
import imutils
from imutils.video import VideoStream, FPS

# --- Konfigurasi Serial ke ESP32 ---
esp = serial.Serial('COM3', 115200, timeout=1)  # Ganti COM4 ke port ESP32 kamu
time.sleep(2)  # Tunggu koneksi serial stabil

# --- Model Deteksi Objek ---
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
	"bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
	"dog", "horse", "motorbike", "person", "pottedplant", "sheep",
	"sofa", "train", "tvmonitor", "tie", "book"]
COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))

print("[INFO] loading model...")
net = cv2.dnn.readNetFromCaffe('MobileNetSSD_deploy.prototxt.txt', 'MobileNetSSD_deploy.caffemodel')

print("[INFO] starting video stream...")
vs = VideoStream(src=2).start()  # ganti ke 0 jika pakai webcam biasa
time.sleep(2.0)
fps = FPS().start()

last_command_time = 0
command_interval = 0.5
last_command_sent = None  # Untuk menghindari pengiriman perintah berulang

while True:
	frame = vs.read()
	frame = imutils.resize(frame, width=400)
	(h, w) = frame.shape[:2]
	frame_center = w // 2

	blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)),
		0.007843, (300, 300), 127.5)
	net.setInput(blob)
	detections = net.forward()

	person_detected = False
	current_time = time.time()

	for i in np.arange(0, detections.shape[2]):
		confidence = detections[0, 0, i, 2]
		if confidence > 0.2:
			idx = int(detections[0, 0, i, 1])
			label_name = CLASSES[idx]
			if label_name not in ["person"]:
				continue

			person_detected = True
			box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
			(startX, startY, endX, endY) = box.astype("int")

			center_x = (startX + endX) // 2

			# Gambar bounding box
			label = "{}: {:.2f}%".format(CLASSES[idx], confidence * 100)
			cv2.rectangle(frame, (startX, startY), (endX, endY), COLORS[idx], 2)
			y = startY - 15 if startY - 15 > 15 else startY + 15
			cv2.putText(frame, label, (startX, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS[idx], 2)

			# Kirim perintah robot jika cukup waktu berlalu
			if current_time - last_command_time >= command_interval:
				if abs(center_x - frame_center) < 40:
					command = b'1'  # Maju
				elif center_x < frame_center:
					command = b'3'  # Belok kiri
				else:
					command = b'2'  # Belok kanan

				if command != last_command_sent:
					esp.write(command)
					print(f"[INFO] Sent command: {command.decode()}")
					last_command_sent = command
				last_command_time = current_time

	# Jika tidak ada objek terdeteksi, kirim berhenti
	if not person_detected and current_time - last_command_time >= command_interval:
		if last_command_sent != b'0':
			esp.write(b'0')
			print("[INFO] Sent command: 0 (STOP)")
			last_command_sent = b'0'
		last_command_time = current_time

	# Tampilkan hasil kamera
	cv2.imshow("Frame", frame)
	key = cv2.waitKey(1) & 0xFF
	if key == ord("q"):
		break

	fps.update()

# Cleanup
fps.stop()
print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))
cv2.destroyAllWindows()
vs.stop()
esp.close()
