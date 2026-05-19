@echo off
:: Shorts Auto Pipeline - 스케줄러 실행 래퍼
:: Windows 작업 스케줄러에서 호출됨 (1개 영상 생성 + YouTube 업로드)

cd /d "D:\Application\Claude\shorts_auto"
"D:\Application\Claude\shorts_auto\.venv\Scripts\python.exe" -m scripts.run_batch --count 1 >> logs\scheduler.log 2>&1
