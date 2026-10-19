# pcensored

**p**ixiv **censor** program — pixiv 업로드용 비공식 검열 도구예요.
(pixiv 공식 도구가 아닙니다)

이미지의 민감한 부위를 자동 탐지해 모자이크 처리하는 도구.
alpha-mask-killer의 알파 합성 로직과 검열 파이프라인을 합친 버전이에요.

이미지 1장당 파이프라인:
1. **알파 합성** — 투명 채널이 있으면 지정 배경색 위에 합성
2. **NSFW 탐지** — 전체 스캔 + 스마트 크롭 4회 (CENTER/LOWER/LEFT/RIGHT)
3. **모자이크** — 탐지 영역에 모자이크 (대상: 여성기·남성기·항문)
4. **WEBP 저장**

Windows / Linux / macOS에서 모두 동작해요.

## 설치

[uv](https://docs.astral.sh/uv/)가 필요해요.

```bash
# 처음 한 번만: 가상환경 + 의존성 설치
uv sync

# GUI 실행 (추천)
uv run pcensored_amk_gui.py

# 명령줄 실행
uv run pcensored_amk.py 입력폴더 -o 출력폴더
```

> 처음이세요? **UV_설치가이드.md**를 먼저 보세요. (Windows/macOS/Linux 설치 안내 포함)

## 탐지 모델 내려받기 (필수)

모델 파일(`ntd11.pt`)은 이 저장소에 들어있지 않아요. 아래 모델 페이지에서 v5.0을 받아
압축을 풀고, 안에 있는 `.pt` 파일을 `ntd11.pt`로 이름을 바꿔
**이 폴더(실행 파일이 있는 폴더)에 넣어주세요.** 변환 과정은 필요 없어요.

- **모델 페이지**: https://civitai.com/models/1313556/anime-nsfw-detection-adetailer-all-in-one

**모델 크레딧**: [newtextdoc1111](https://civitai.com/user/newtextdoc1111)의
Anime NSFW Detection / ADetailer All-in-One (v5.0, Apache License) 모델을 사용합니다.

## 사용법

```bash
# 폴더 일괄 처리
uv run pcensored_amk.py 입력폴더 -o 출력폴더

# 1장만
uv run pcensored_amk.py 이미지.png -o 출력폴더

# 옵션
uv run pcensored_amk.py 입력폴더 -o 출력폴더 \
  --confidence 0.3 --block 24 --padding 20 --quality 90 \
  --bg ff0000 --threads 8
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--confidence` | 0.10 | 탐지 신뢰도 임계값 |
| `--block` | 20 | 모자이크 강도 (클수록 강함) |
| `--padding` | 15 | 탐지 박스 확장(px) |
| `--quality` | 95 | WEBP 품질 |
| `--bg` | ffffff | 알파 합성 배경색 (hex) |
| `--no-smart-crop` | 끔 | 스마트 크롭 끄기 (약 5배 빠름) |
| `--threads` | 4 | ONNX 스레드 수 |

출력: `{원본이름}_censored.webp`

## 속도 참고

1장당 추론 5회(전체 1 + 크롭 4)라 CPU에서는 수십 초 걸려요.
`--no-smart-crop`을 쓰면 1회 추론이라 훨씬 빨라요.

## 라이선스

MIT License — 자세한 내용은 [LICENSE](LICENSE) 파일을 보세요.
