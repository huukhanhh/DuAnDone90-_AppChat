@echo off
chcp 65001 >nul
echo ==============================================
echo Cai dat cac thu vien cho Chat Application
echo ==============================================
echo.

echo [1/12] Installing PySide6 (GUI Framework)...
pip install PySide6

echo.
echo [2/12] Installing MySQL Connector...
pip install mysql-connector-python

echo.
echo [3/12] Installing Bcrypt (Password Security)...
pip install bcrypt

echo.
echo [4/12] Installing Google Generative AI (Gemini Chatbot)...
pip install google-generativeai

echo.
echo [5/12] Installing Markdown (Text Formatting)...
pip install markdown

echo.
echo [6/12] Installing PyAudio (Audio Call Features)...
pip install pyaudio

echo.
echo [7/12] Installing Transformers (AI Content Moderation)...
pip install transformers

echo.
echo [8/12] Installing PyTorch CPU (AI Backend)...
pip install torch --index-url https://download.pytorch.org/whl/cpu

echo.
echo [9/12] Installing OpenCV (Camera/Image Processing for FaceID)...
pip install opencv-python

echo.
echo [10/12] Installing NumPy (Numerical Computing)...
pip install numpy

echo.
echo [11/12] Installing DeepFace (Face Recognition)...
pip install deepface

echo.
echo [12/12] Installing TensorFlow (DeepFace Backend)...
pip install tensorflow

echo.
echo ==============================================
echo CAI DAT HOAN TAT!
echo ==============================================
echo.
echo Cac thu vien da cai dat:
echo   - PySide6          : Giao dien nguoi dung
echo   - mysql-connector  : Ket noi database
echo   - bcrypt           : Ma hoa mat khau
echo   - google-generativeai : Gemini AI Chatbot
echo   - markdown         : Dinh dang text
echo   - pyaudio          : Goi thoai (Audio Call)
echo   - transformers     : Kiem duyet noi dung AI
echo   - torch            : Backend cho AI
echo   - opencv-python    : Xu ly camera/anh
echo   - numpy            : Xu ly mang so
echo   - deepface         : Nhan dien khuon mat
echo   - tensorflow       : Backend cho DeepFace
echo.
pause
