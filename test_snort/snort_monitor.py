import os
import time
import glob
import subprocess
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class SnortLogHandler(FileSystemEventHandler):
    def __init__(self):
        self.processed_files = {}  # {파일경로: 마지막처리된크기}
        # 현재 스크립트가 있는 디렉토리에 로그 파일 저장
        self.output_file = os.path.join(os.path.dirname(__file__), 'snort_logs.txt')
        
    def on_created(self, event):
        """새 파일 생성 감지"""
        if event.is_directory:
            return
        
        if event.src_path.startswith("/var/log/snort/snort.log."):
            self.process_log_file(event.src_path)
    
    def on_modified(self, event):
        """파일 수정 감지"""
        if event.is_directory:
            return
            
        if event.src_path.startswith("/var/log/snort/snort.log."):
            self.process_log_file(event.src_path, check_size=True)
    
    def process_existing_logs(self):
        """기존 로그 파일들을 처리"""
        log_files = glob.glob("/var/log/snort/snort.log.*")
        for log_file in log_files:
            self.process_log_file(log_file)

    def process_log_file(self, log_file, check_size=False):
        """개별 로그 파일 처리"""
        try:
            current_size = os.path.getsize(log_file)
            
            # 파일이 비어있으면 건너뛰기
            if current_size == 0:
                logger.info(f"Skipped empty log file: {log_file}")
                return
                
            # 이미 처리된 파일이고 크기가 변경되지 않았다면 건너뛰기
            if check_size and log_file in self.processed_files:
                if current_size <= self.processed_files[log_file]:
                    return
                    
            # 파일이 완전히 쓰여질 때까지 잠시 대기
            time.sleep(1)
            
            # 새로운 내용만 처리
            last_processed_size = self.processed_files.get(log_file, 0)
            if current_size > last_processed_size:
                # u2spewfoo 명령어로 전체 로그 파일 처리
                cmd = ['u2spewfoo', log_file]
                
                # 임시 파일에 전체 출력 저장
                temp_output = os.path.join(os.path.dirname(__file__), 'temp_snort_logs.txt')
                with open(temp_output, 'w') as f:
                    subprocess.run(cmd, stdout=f, check=True)
                
                # 새로운 내용만 추출하여 기존 로그 파일에 추가
                with open(temp_output, 'r') as temp_file:
                    with open(self.output_file, 'a') as main_file:
                        # 파일의 끝부분에 새로 추가된 로그만 처리
                        main_file.write("\n----- New Log Entries -----\n")
                        main_file.write(f"Source file: {log_file}\n")
                        main_file.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        main_file.write(temp_file.read())
                
                # 임시 파일 삭제
                os.remove(temp_output)
                
                # 처리된 크기 업데이트
                self.processed_files[log_file] = current_size
                logger.info(f"Processed log file: {log_file} (size: {current_size} bytes)")
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Error processing {log_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing {log_file}: {e}")

def main():
    # 이벤트 핸들러 및 옵저버 설정
    event_handler = SnortLogHandler()
    observer = Observer()
    observer.schedule(event_handler, "/var/log/snort", recursive=False)
    observer.start()

    # 기존 로그 파일들 처리
    event_handler.process_existing_logs()
    
    logger.info("Started monitoring Snort log directory...")
    
    try:
      	while True:
         	time.sleep(1)
    except KeyboardInterrupt:
       	observer.stop()
       	logger.info("Stopping monitor...")
    
    observer.join()

if __name__ == "__main__":
    main()
