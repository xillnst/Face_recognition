import face_recognition
import os
import numpy as np

faces_folder = "faces"
known_encodings = []
student_names = []
student_classes = []

for class_name in os.listdir(faces_folder):
    class_folder = os.path.join(faces_folder, class_name)
    if not os.path.isdir(class_folder):
        continue
    for file in os.listdir(class_folder):
        path = os.path.join(class_folder, file)
        name = os.path.splitext(file)[0]
        image = face_recognition.load_image_file(path)
        enc = face_recognition.face_encodings(image)
        if len(enc) == 0:
            print(f"Warning: No face found in {path}")
            continue
        known_encodings.append(enc[0])
        student_names.append(name)
        student_classes.append(class_name)

# Сохраняем кодировки и имена для последующего использования
np.save("known_encodings.npy", known_encodings)
np.save("student_names.npy", student_names)
np.save("student_classes.npy", student_classes)

print("Saved encodings for", len(student_names), "students")