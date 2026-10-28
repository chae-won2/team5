# 배포·DB·메일 운영

기준: 2026-10-23. 배포 브랜치는 `codex/deploy-render`, 서비스는 https://busan-full-course.onrender.com/ 입니다.

## Render

Docker 다단계 빌드로 React를 빌드하고 FastAPI가 `frontend/dist`를 제공합니다. `/api`는 같은 서버를 사용하므로 공개 환경에 로컬 `127.0.0.1:8000` 주소를 넣지 않습니다. `VITE_API_BASE_URL`은 별도 API 서버를 사용할 때만 필요합니다.

```powershell
git push origin codex/deploy-render
```

푸시 후 Render에서 해당 커밋이 Live인지 확인합니다. `render.yaml`은 구성 명세이며 기존 수동 생성 서비스의 비밀값을 자동으로 채우지 않습니다. `.env`·원천 전체·노출 SQLite는 이미지에 넣지 않습니다. Docker는 최종 장소·가맹점·부산의 맛 자료만 필요한 경로로 복사합니다.

Render 서버 환경변수: `KAKAO_REST_API_KEY`, `TMAP_APP_KEY`, `BREVO_API_KEY`, `EMAIL_FROM`, `EMAIL_DELIVERY_ENABLED=true`, `EXPOSURE_DATABASE_URL`, `ADMIN_DASHBOARD_KEY`(`/admin` 운영 대시보드 접근 키). 비밀값을 README·GitHub·프런트 변수에 붙이지 않습니다.

## Supabase 영속 노출 기록

노출 전용 프로젝트는 `busan-full-course-exposure`입니다. `supabase/exposure.sql`로 비공개 `app_private.exposure_lists`·`app_private.exposure_candidates`와 인덱스를 생성합니다. Data API는 사용하지 않으며 public/anon/authenticated 테이블 접근을 차단했습니다. 기존 `supabase/schema.sql`은 과거 원천 적재 테이블용으로 별개입니다.

FastAPI는 `EXPOSURE_DATABASE_URL`로 SSL 필수 연결합니다. 현재 IPv4 호환 세션 풀러 5432를 사용합니다. 새 DB/환경으로 옮기면 해당 프로젝트 Connect 화면에서 연결 문자열을 다시 확인하세요. `scripts/configure_exposure_db.py`는 현재 프로젝트의 기존 DB 비밀번호를 로컬 터미널에서 입력받아 URL 인코딩 후 `.env`에 저장하는 전용 설정 도구입니다. 비밀번호를 출력하지 않습니다.

Render에서 URL이 없거나 DB에 연결하지 못하면 기록을 로컬 파일로 조용히 대체하지 않고 관련 API가 503을 반환합니다. 로컬에서 URL이 없으면 `backend/var/exposure.sqlite3`를 사용합니다. 기존 SQLite는 자동 이관하지 않습니다.

확인된 노출 이력은 보관하고 순환 집계만 최근 7일로 제한합니다. 표시되지 않은 신규 요청도 후보·배정 분석을 위해 보관합니다. 표시 확인은 발급 후 1시간 이내에만 허용합니다. Supabase 무료 프로젝트는 비활성 기간에 일시 중지될 수 있으므로 운영·발표 전에 상태를 확인합니다. 별도 백업·보관 정책과 대시보드는 아직 없습니다.

## 메일

공개 서버는 Brevo HTTPS API를 사용합니다. Gmail SMTP 설정이 없어도 `BREVO_API_KEY`·`EMAIL_FROM`이 있으면 발송합니다. Gmail SMTP는 별도 환경용 호환 경로이며 현재 무료 Render의 기본 운영 방식이 아닙니다.

메일 주소 이용 동의가 있어야 발송합니다. 한국어·영어·일본어·번체를 지원하고 공식 외국어명이 확인되지 않은 상호는 한국어를 유지하고 자동 로마자 표기를 보조로 붙입니다. 메일에 장소별 주소와 자체 코스 재열기 링크를 포함하며, 하단 Google Maps 전체 방문순서 링크는 제공하지 않습니다. 코스 재열기 시 이동시간을 재계산합니다. 설정 시간보다 최대 10분 초과한 코스까지 다시 열 수 있습니다.

정상 API 응답은 발송 서비스의 접수 확인이며 수신함 도착을 보장하지 않습니다. 실패 시 서버 상태 코드·Brevo 전송 로그·발신자 인증·쿼터를 확인하고 비밀값이나 수신자 정보를 로그에 출력하지 않습니다. 실제 테스트 메일은 수신자와 발송 횟수를 확인한 뒤 보냅니다.

## 점검

- `/api/health`: 웹 서버 응답 확인. 이 응답만으로 DB·외부 API 연결 성공을 단정하지 않습니다.
- `/api/recommend/next`: TMAP 경로·후보·목록 ID 생성 확인.
- `/api/recommend/impressions`: 서버 발급 ID만 허용하고 중복은 한 번만 기록하는지 확인.
- DB는 별도 연결에서 기록이 유지되는지 확인합니다. 테스트 기록은 실제 노출 통계와 섞지 않습니다.
- 이메일 500 오류는 본문 생성도 확인합니다. `course_link`는 모든 언어에 있어야 합니다.
- 시간 초과는 설정값 +10분까지만 허용합니다. 장소 ID·중복·직전 장소에서 도보 20분 조건도 적용하며, 업종별 방문 횟수 제한은 없습니다.

### 추천 기록 스키마 보완

배포 전에 `python scripts/migrate_exposure_db.py`로 요청 정책·조건 컬럼과 `app_private.exposure_candidates`를 생성합니다. 기존 이력은 보존합니다. 실제 후보 기록은 해당 코드 배포 이후 생성되는 요청부터 쌓입니다. 최근 7일 순환 규칙은 그대로이며 실험(`simulation`) 기록은 운영 집계에서 제외됩니다.
