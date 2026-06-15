@echo off
chcp 65001 >nul
echo ========================================
echo   말랑몰랑 빌드 스크립트
echo ========================================
echo.

:: Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않거나 PATH에 없습니다.
    echo        https://python.org/downloads 에서 설치하세요.
    pause
    exit /b 1
)

:: PyInstaller 설치 확인 및 설치
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [설치] PyInstaller를 설치합니다...
    pip install pyinstaller
    echo.
)

:: 의존성 설치
echo [1/3] 의존성 설치 중...
pip install -r requirements.txt
echo.

:: 빌드
echo [2/3] exe 빌드 중... (1~3분 소요)
pyinstaller mallangmollang.spec --noconfirm
echo.

if errorlevel 1 (
    echo [오류] 빌드 실패. 위의 에러 메시지를 확인하세요.
    pause
    exit /b 1
)

:: 결과 안내
echo [3/3] 빌드 완료!
echo.
echo   출력 폴더: dist\MallangMollang\
echo   실행 파일: dist\MallangMollang\MallangMollang.exe
echo.
echo   ※ Tesseract OCR이 별도로 설치되어 있어야 합니다.
echo     https://github.com/UB-Mannheim/tesseract/wiki
echo.
pause
