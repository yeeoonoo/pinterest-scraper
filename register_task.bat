@echo off
REM Pinterest Scraper - Windows 작업 스케줄러 등록
REM 관리자 권한으로 실행 필요

set SCRIPT_DIR=%~dp0
set PYTHON_PATH=python
set TASK_NAME=PinterestScraper

echo [작업 스케줄러 등록 중...]

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%main.py\"" ^
  /sc daily ^
  /st 09:00 ^
  /rl highest ^
  /f

if %errorlevel% == 0 (
    echo [완료] 매일 오전 9시에 실행되도록 등록되었습니다.
    echo 작업 확인: schtasks /query /tn "%TASK_NAME%"
) else (
    echo [오류] 등록 실패. 관리자 권한으로 다시 실행해주세요.
)

pause
