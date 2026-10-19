# uv 설치 가이드 (초보자용)

pcensored-amk를 실행하려면 `uv`라는 파이썬 도구 관리자가 필요해요.
5분이면 설치돼요.

---

## 1단계: uv 설치

### Windows

1. 키보드의 `Win + R`을 누르고 `powershell`을 입력한 뒤 엔터
2. 아래 명령을 복사해서 붙여넣고 엔터

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

3. 파워셸을 껐다가 다시 켜세요

### macOS / Linux

1. 터미널을 여세요
2. 아래 명령을 복사해서 붙여넣고 엔터

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. 터미널을 껐다가 다시 켜세요

### 설치 확인

터미널(파워셸)에 아래를 입력했을 때 버전이 나오면 성공이에요.

```bash
uv --version
```

---

## 2단계: pcensored-amk 실행

1. `pcensored-amk-v0.1.0.zip` 압축을 풀어요
2. 압축 푼 폴더에서 터미널을 열어요
   - **Windows**: 폴더 주소창에 `powershell`을 입력하고 엔터
   - **macOS**: 폴더에서 우클릭 → "새로운 터미널" (또는 터미널에 폴더를 드래그)
   - **Linux**: 폴더에서 우클릭 → "터미널에서 열기"
3. 처음 한 번만 아래 명령으로 필요한 것들을 설치해요 (1~2분)

```bash
uv sync
```

4. 이제 실행해요! GUI 버전을 추천해요.

```bash
uv run pcensored_amk_gui.py
```

창이 뜨면 버튼으로 파일/폴더를 고르고, 슬라이더로 옵션을 조절한 뒤 실행을 누르세요.

<details>
<summary>명령줄 버전 (고급 사용자용)</summary>

```bash
uv run pcensored_amk.py 입력폴더 -o 출력폴더
```

예시:

```bash
# 내 사진 폴더의 이미지들을 output 폴더에 저장
uv run pcensored_amk.py "C:\Users\내이름\Pictures\생성그림" -o output
```

</details>

---

## 자주 묻는 질문

**Q. `uv`를 찾을 수 없다고 나와요**
→ 터미널을 완전히 껐다가 다시 켜보세요. 그래도 안 되면 컴퓨터를 재시작하세요.

**Q. `uv sync`가 오래 걸려요**
→ 처음 한 번만 받는 거예요. 다음부터는 바로 실행돼요.

**Q. 검열이 너무 느려요 (1장에 1분 이상)**
→ `--no-smart-crop` 옵션을 붙여보세요. 약 5배 빨라져요.

```bash
uv run pcensored_amk.py 입력폴더 -o 출력폴더 --no-smart-crop
```

**Q. 검열이 너무 약해요 / 너무 강해요**
→ `--confidence` 값을 조절하세요. 낮을수록 많이 잡아요.

```bash
uv run pcensored_amk.py 입력폴더 -o 출력폴더 --confidence 0.15
```
