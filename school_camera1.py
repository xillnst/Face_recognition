import face_recognition
import cv2
import os
import csv
from datetime import datetime
import smtplib
from email.message import EmailMessage
import winsound

# ---------------- EMAIL ----------------
EMAIL = "YOUR EMAIL"
PASSWORD = "PASSWORD"
DIRECTOR_EMAIL = "EMAIL"

START_TIME = "08:30"      # Время начала урока
AUTO_REPORT_TIME = "08:45"  # Время автоматического отчета

# ---------------- FUNCTIONS ----------------
def send_unknown_alert(photo_path):
    msg = EmailMessage()
    msg["Subject"] = "⚠️ НЕИЗВЕСТНЫЙ ЧЕЛОВЕК ОБНАРУЖЕН"
    msg["From"] = EMAIL
    msg["To"] = DIRECTOR_EMAIL
    msg.set_content("Неизвестный человек был обнаружен камерой школы")

    with open(photo_path,"rb") as f:
        msg.add_attachment(f.read(), maintype="image", subtype="jpeg", filename="unknown.jpg")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465) as smtp:
            smtp.login(EMAIL,PASSWORD)
            smtp.send_message(msg)
        print("Сигнал об неизвестном отправлен")
    except Exception as e:
        print("Ошибка при отправке email:", e)

def send_report():
    report = "ОТЧЁТ ПОСЕЩАЕМОСТИ ШКОЛЫ\n\n"
    class_present = {}
    class_total = {}
    late_students_info = {}
    today_str = datetime.now().strftime("%Y-%m-%d")

    for cls in student_classes:
        class_total[cls] = class_total.get(cls, 0) + 1

    for name in seen_students:
        index = student_names.index(name)
        cls = student_classes[index]
        class_present[cls] = class_present.get(cls, 0) + 1

    attendance_times = {}
    if os.path.exists("attendance.csv"):
        with open("attendance.csv") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split(",")
                if len(parts) == 4:
                    student_name, student_class_csv, time_arrived, status = parts
                    if not time_arrived.startswith(today_str):
                        continue
                    attendance_times[student_name] = time_arrived.split(" ")[1]
                    if status == "Late":
                        late_students_info[student_name] = time_arrived.split(" ")[1]

    for cls in sorted(set(student_classes)):
        report += f"Класс {cls}\n"
        present = class_present.get(cls, 0)
        total = class_total[cls]
        absent = total - present
        report += f"Присутствуют: {present}\nОтсутствуют: {absent}\n\n"

        report += "Список присутствующих:\n"
        for name in seen_students:
            index = student_names.index(name)
            if student_classes[index] == cls:
                time_arrived = attendance_times.get(name, "неизвестно")
                status = " (опоздал)" if name in late_students_info else ""
                report += f"{name} (пришёл в {time_arrived}){status}\n"

        report += "\nСписок отсутствующих:\n"
        for name, student_class in zip(student_names, student_classes):
            if student_class == cls and name not in seen_students:
                report += name + "\n"

        report += "\n-----------------\n\n"

    report += "Опоздавшие ученики:\n"
    if len(late_students_info) == 0:
        report += "Нет\n"
    else:
        for name, time_arrived in late_students_info.items():
            index = student_names.index(name)
            cls = student_classes[index]
            report += f"{name} ({cls}) — пришёл в {time_arrived}\n"

    msg = EmailMessage()
    msg["Subject"] = "Отчёт посещаемости школы"
    msg["From"] = EMAIL
    msg["To"] = DIRECTOR_EMAIL
    msg.set_content(report)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL, PASSWORD)
            smtp.send_message(msg)
        print("Отчёт отправлен директору")
    except Exception as e:
        print("Ошибка при отправке письма:", e)

# ---------------- LOAD STUDENTS ----------------
faces_folder = "faces"
known_encodings=[]
student_names=[]
student_classes=[]

for class_name in os.listdir(faces_folder):
    class_path = os.path.join(faces_folder, class_name)
    if not os.path.isdir(class_path):
        continue
    for file in os.listdir(class_path):
        path = os.path.join(class_path, file)
        name = os.path.splitext(file)[0]
        image = face_recognition.load_image_file(path)
        enc = face_recognition.face_encodings(image)
        if len(enc)==0:
            continue
        known_encodings.append(enc[0])
        student_names.append(name)
        student_classes.append(class_name)

print("Loaded students:", len(student_names))

# ---------------- MEMORY ----------------
seen_students = set()
class_counters = {}
unknown_timer = None
unknown_sent = False
report_sent_today = False
process_frame = True
current_day = datetime.now().day

# ---------------- CREATE CSV IF NOT EXISTS ----------------
if not os.path.exists("attendance.csv"):
    with open("attendance.csv","w",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name","Class","TimeArrived","Status"])

# ---------------- CAMERA ----------------
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)

if not cap.isOpened():
    print("Camera cannot open!")
    exit()

while True:
    now = datetime.now()
    # ---------------- RESET MEMORY EACH DAY ----------------
    if now.day != current_day:
        seen_students.clear()
        class_counters.clear()
        report_sent_today = False
        current_day = now.day
        print("Новая дата, счетчики сброшены")

    ret,frame = cap.read()
    if not ret:
        print("Failed to grab frame")
        break

    small = cv2.resize(frame,(0,0),fx=0.25,fy=0.25)
    rgb = cv2.cvtColor(small,cv2.COLOR_BGR2RGB)

    if process_frame:
        locations = face_recognition.face_locations(rgb, model="hog")
        encodings = face_recognition.face_encodings(rgb, locations, num_jitters=0)
        unknown_detected=False

        for (top,right,bottom,left),encoding in zip(locations,encodings):
            matches = face_recognition.compare_faces(known_encodings,encoding, tolerance=0.5)
            name="Unknown"
            student_class=""
            status=""

            if True in matches:
                index = matches.index(True)
                name = student_names[index]
                student_class = student_classes[index]

                if name not in seen_students:
                    seen_students.add(name)
                    now_time = now.strftime("%Y-%m-%d %H:%M:%S")
                    status = "Late" if now.strftime("%H:%M") > START_TIME else "Present"

                    with open("attendance.csv","a",newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([name, student_class, now_time, status])

                    class_counters[student_class] = class_counters.get(student_class,0)+1
                    print(name,"arrived",student_class,status)
            else:
                unknown_detected=True

            top*=4; right*=4; bottom*=4; left*=4
            color=(0,0,255) if status=="Late" else (0,255,0) if name!="Unknown" else (0,0,255)
            cv2.rectangle(frame,(left,top),(right,bottom),color,2)
            cv2.putText(frame,name,(left,top-10),cv2.FONT_HERSHEY_SIMPLEX,0.9,color,2)

        if unknown_detected:
            cv2.putText(frame,"UNKNOWN DETECTED!",(50,80),cv2.FONT_HERSHEY_SIMPLEX,1.2,(0,0,255),3)
            if unknown_timer is None:
                unknown_timer = now
            elapsed = (now-unknown_timer).total_seconds()
            if elapsed>=3 and not unknown_sent:
                if not os.path.exists("unknown"):
                    os.makedirs("unknown")
                filename = f"unknown/unknown_{int(now.timestamp())}.jpg"
                cv2.imwrite(filename,frame)
                for i in range(8):
                    winsound.Beep(3000,400)
                send_unknown_alert(filename)
                unknown_sent=True
        else:
            unknown_timer=None
            unknown_sent=False

    process_frame = not process_frame

    y=30
    for cls in sorted(set(student_classes)):
        total = student_classes.count(cls)
        present = class_counters.get(cls, 0)
        text = f"{cls}: {present}/{total}"
        cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        y += 30

    current_time = datetime.now().strftime("%H:%M")
    if current_time == AUTO_REPORT_TIME and not report_sent_today:
        send_report()
        report_sent_today = True

    cv2.imshow("School Camera", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == 27:
        break
    if key == ord("r"):
        send_report()

cap.release()
cv2.destroyAllWindows()