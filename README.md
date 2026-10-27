# GBDK Game Harness

자연어 게임 설명을 OpenAI 호환 Chat Completions API로 전달해 명세를 만들고, 이미지 생성, GBDK-2020 에셋 변환, ROM 빌드, 에뮬레이터 실행까지 연결하는 파이썬 하네스입니다. `gb-harness`는 오리지널 Game Boy용, `gbc-harness`는 Game Boy Color용입니다.

## 필요한 것

- Python 3.9 이상
- 게임 설명을 생성할 OpenAI API 호환 서비스의 API 키와 모델
- 이미지 생성용 OpenAI 이미지 모델 (이미지 생성 단계를 사용할 경우)
- Pillow (`pip install -r requirements.txt`)
- 실제 Game Boy ROM 빌드/실행 시 GBDK-2020 (`tools/gbdk`에 포함)
- ROM 실행 시 mGBA (`tools/mgba`에 포함)

이미지 정규화에는 Pillow가 필요합니다. GBDK-2020은 파이썬 패키지가 아니라 별도 개발 도구이며, 이 프로젝트에는 공식 4.5.0 Intel macOS 배포본이 `tools/gbdk`에 설치되어 있습니다. `lcc`와 `png2asset`은 `tools/gbdk/bin`에 있습니다. mGBA 0.10.5 유니버설 macOS 앱은 `tools/mgba/mGBA.app`에 포함되어 있으며, CLI 디버거와 GDB remote server도 사용할 수 있습니다.

## 실행

```sh
export OPENAI_API_KEY="your-api-key"
python -m gb_harness "주인공이 오른쪽과 왼쪽으로 움직이며 동전을 줍는 게임"
```

Game Boy Color ROM은 별도 모듈로 실행합니다:

```sh
python -m gbc_harness --generate-images --build --run \
  "컬러 팔레트가 있는 주인공이 동전을 줍는 게임"
```

`gbc-harness` 진입점은 GBC를 기본 타깃으로 선택합니다. 일반 하네스에서 `--platform gbc`를 지정해도 같은 타깃을 사용할 수 있습니다. GBC 빌드에는 GBDK의 CGB 헤더/팔레트/배경 타일 속성을 적용하고 `.gbc` ROM을 출력합니다. GBC 전용 이미지 정규화는 타일을 15-bit RGB로 변환하고, 배경 타일마다 최대 4색 팔레트를 선택해 화면 전체에 최대 8개 배경 팔레트를 사용합니다. 스프라이트는 각각 최대 4색 팔레트를 사용하며 최대 8개까지 생성할 수 있습니다. 따라서 투명 스프라이트 색을 제외하면 배경 32색 + 오브젝트 24색, 즉 화면에 최대 56색을 표시할 수 있는 하드웨어 한도에 맞춥니다.

명세 생성부터 이미지 생성, PNG 에셋 변환, ROM 빌드, 에뮬레이터 실행까지 한 번에 하려면:

```sh
python -m gbc_harness \
  --generate-images --build --run \
  "주인공이 오른쪽과 왼쪽으로 움직이며 동전을 줍는 게임"
```

이미지 생성과 빌드는 각각 선택할 수 있습니다. `--build`는 `assets/<asset_id>.png` 파일이 이미 있어야 하고, `--run`은 ROM을 빌드한 뒤 기본 포함된 mGBA를 실행합니다. 다른 실행 파일을 사용하려면 `--emulator` 또는 `GB_EMULATOR`를 지정합니다. 이미지 생성 모델은 `--image-model` 또는 `OPENAI_IMAGE_MODEL`로 지정할 수 있으며, 이미지 생성 API 호출에는 추가 비용이 발생할 수 있습니다.

디버깅:

```sh
# mGBA 대화형 CLI 디버거
python -m gbc_harness --build --run --emulator-debugger

# IDE/자동화용 GDB remote server (localhost:2345)
python -m gbc_harness --build --run --gdb-server
```

mGBA GDB server에 연결하는 GDB 클라이언트는 별도로 준비해야 합니다. GDB 프로토콜 클라이언트가 연결되면 브레이크포인트와 레지스터/메모리 조사 등 mGBA 디버깅 기능을 사용할 수 있습니다.

특정 OpenAI 호환 API를 사용하거나 출력 위치/모델을 바꾸려면:

```sh
python -m gb_harness "간단한 점프 게임" \
  --api-base-url "https://api.openai.com/v1" \
  --model "gpt-4o-mini" \
  --output generated_game
```

기본 API 주소와 모델은 각각 `OPENAI_BASE_URL`, `OPENAI_MODEL` 환경 변수로도 지정할 수 있습니다. API 키는 `OPENAI_API_KEY`에서 읽습니다.

생성 결과:

- `generated_game/game_spec.json`: 검증된 전체 JSON 명세
- `generated_game/main.c`: 설계도 C 템플릿과 생성된 로직 조각
- `generated_game/assets/asset_prompts.json`: 이미지 생성용 프롬프트 목록

`--generate-images`는 OpenAI 이미지 API에서 PNG를 받아옵니다. 빌드 시 스프라이트는 `move_sprite()`와 호환되는 단일 8x8 하드웨어 스프라이트로 맞추고 흰 배경을 투명 처리합니다. DMG 이미지는 기존 4색 정규화를 사용합니다. GBC 이미지는 별도의 [GBC 정규화기](./gb_harness/gbc_image_normalizer.py)에서 타일별 팔레트 양자화와 15-bit RGB 색상 맞춤을 수행하고, 배경은 80x72로 축소 후 2배 nearest-neighbor로 확대합니다. GBDK `png2asset`은 CGB map palette 속성과 팔레트 배열을 생성하고, C 초기화 코드가 생성된 전체 팔레트를 로드합니다. AI가 만든 이미지와 게임 로직은 추가 편집이 필요할 수 있습니다.

파이썬 의존성은 다음으로 설치합니다:

```sh
python -m pip install -r requirements.txt
```

GBDK-2020 라이선스와 배포 문서는 `tools/gbdk/licenses` 및 `tools/gbdk/README`에 포함되어 있습니다.

## 테스트

```sh
python -m unittest discover -s tests
```
