"""
더블클릭 실행용 진입 스크립트.
한글 입력/출력을 안정적으로 처리한다.
"""

import sys
import io

# Windows 터미널 한글 입출력 보장
sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8", errors="replace")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import main  # noqa: E402 (stdout 재설정 후 import 필요)


def ask_keyword() -> str:
    while True:
        try:
            keyword = input("검색할 키워드를 입력하세요: ").strip()
        except UnicodeDecodeError:
            print("입력을 읽지 못했습니다. 다시 시도해주세요.")
            continue

        if not keyword:
            print("키워드를 입력해주세요.\n")
            continue

        confirm = input(f'"{keyword}" 으로 검색합니다. 맞으면 Enter, 다시 입력하려면 n: ').strip().lower()
        if confirm == "n":
            print()
            continue

        return keyword


if __name__ == "__main__":
    keyword = ask_keyword()

    # main.py의 run()을 키워드 인자와 함께 호출
    sys.argv = ["main.py", keyword]
    main.run()
