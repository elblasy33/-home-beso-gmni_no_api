# Browser AI Automation Agent ⚡

> **A Production-Ready, Configuration-Driven Browser Automation Platform built with Python, Playwright, and FastAPI.**

---

## 🌟 نظرة عامة (Overview)

تم تصميم **Browser AI Automation Agent** ليكون محركًا عامًا (Generic Engine) لأتمتة التعامل مع مواقع الذكاء الاصطناعي وبوابات المحادثة ونماذج الويب المختلفة دون الحاجة لكتابة كود جديد لكل موقع. 

الموقع بالكامل يعتمد على **Site Configurations (ملفات YAML)** تحدد عناصر الإدخال، وأزرار الإرسال، ومناطق الردود، وأماكن رفع المرفقات المتعددة.

---

## 🏗️ الهيكلية المعمارية (Architecture)

```
                    ┌────────────────────────────────────────┐
                    │          Web Application UI            │
                    │  - URL / Prompt / Config Picker        │
                    │  - Dynamic Multi-Attachment Routing    │
                    │  - Live Execution Logs & Live Stream   │
                    │  - Debug & Inspector / Config Recorder │
                    │  - Headed/Headless Toggle & Status     │
                    └───────────────────┬────────────────────┘
                                        │ (HTTP REST + SSE)
                                        ▼
                    ┌────────────────────────────────────────┐
                    │            FastAPI Backend             │
                    │  - /api/jobs (CRUD, Submit, Resume)    │
                    │  - /api/browser (Status, Login, Debug) │
                    │  - /api/configs (YAML Site Adapters)   │
                    │  - /api/recorder (Generate Configs)    │
                    └───────────────────┬────────────────────┘
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │       Async Job Worker & State Machine │
                    │  - States: queued ➔ starting ➔        │
                    │    login_required ➔ navigating ➔       │
                    │    uploading ➔ sending ➔               │
                    │    waiting_response ➔ completed/failed │
                    └───────────────────┬────────────────────┘
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │       Playwright Browser Engine        │
                    │  - Persistent Context (User Data Dir)  │
                    │  - Config-driven Selector Locators     │
                    │  - Multi-target File Setter            │
                    │  - Explicit State Detection & Waits    │
                    │  - Screenshot / Trace / Error Capture  │
                    └───────────────────┬────────────────────┘
                                        │
                       ┌────────────────┴────────────────┐
                       ▼                                 ▼
              [ Local Mock AI Site ]             [ Real Web Sites ]
              - 2FA/Login simulator               - ChatGPT, Claude,
              - Multi-upload zones                - Custom Web Portals,
              - Streaming response                - Form platforms
```

---

## ✨ الميزات الرئيسية (Key Features)

1. **Configuration-Driven (قابل للتهيئة بالكامل)**:
   - عناصر الموقع لا يتم كتابتها في الكود (Hard-coded).
   - لكل موقع ملف إعدادات YAML يحدد روابطه، محددات الإدخال، وأماكن الرفع، وشروط انتظار الرد.

2. **Dynamic Multi-Attachment Routing (توجيه المرفقات المتعددة)**:
   - دعم رفع أكثر من ملف إلى أماكن مختلفة في نفس الصفحة:
     - `Attachment A` ➔ `input#document-upload`
     - `Attachment B` ➔ `input#image-upload`
     - `Attachment C` ➔ `input#data-upload`
   - يمكن للمستخدم اختيار الملف ومكان توجيهه مباشرة من واجهة الويب.

3. **Persistent Browser Session (جلسة متصفح دائمة)**:
   - استخدام `launch_persistent_context` لحفظ الكوكيز والـ Sessions والـ LocalStorage داخل `data/browser_profile/`.
   - لا حاجة لإعادة تسجيل الدخول في كل تشغيل.

4. **Human-in-the-loop 2FA / OTP / CAPTCHA (التعامل التفاعلي مع تسجيل الدخول)**:
   - عند اكتشاف صفحة تسجيل دخول أو كابتشا أو رمز 2FA، يتوقف الـ Agent مؤقتًا ويتحول لحالة `login_required`.
   - تظهر إشارة في واجهة الويب تنبه المستخدم لإكمال التحقق يدويًا في المتصفح.
   - بمجرد الانتهاء، يضغط المستخدم على زر **"Confirm & Resume"** ليستمر الـ Agent دون كسر الأمان.

5. **Decoupled Job Queue (فصل المهام عن الـ Web Requests)**:
   - معالجة المتصفح تتم في Background Worker مستقل بنظام Queued Jobs.
   - لا تتجمد طلبات الـ HTTP، وتتحدث حالة المهمة وسجلاتها في الوقت الحقيقي عبر Server-Sent Events (SSE).

6. **Site Recorder & Element Inspector (تسجيل وضبط المواقع الجديدة)**:
   - وضع تفاعلي يفتح المتصفح مع حقن Inspector Script.
   - يسجل النقرات، وحقول النصوص، وحقول الرفع، ومناطق الردود، ثم يولد ملف إعدادات YAML تلقائيًا.

7. **Local Mock AI Portal (موقع تجريبي محلي متكامل)**:
   - مزود بموقع محلي يحاكي تسجيل الدخول، والـ 2FA، وثلاثة حقول رفع ملفات مستقلة، والرد المتدفق (Streaming) لاختبار كامل الـ Pipeline بدون الحاجة لخدمات خارجية أو بيانات حقيقية.

---

## 🚀 التثبيت والتشغيل السريع (Quickstart)

### 1. المتطلبات (Prerequisites)
- Python 3.10+ (أو استخدام Docker).

### 2. التثبيت المحلي (Local Installation)

```bash
# إنشاء بيئة عمل افتراضية وتفعيلها
python3 -m venv .venv
source .venv/bin/activate

# تثبيت المكتبات المطلوبة
pip install -r requirements.txt

# تثبيت متصفح Chromium
playwright install chromium
```

### 3. التشغيل (Running the Server)

```bash
# تشغيل التطبيق في وضع Headless (الافتراضي)
python run.py

# أو تشغيل التطبيق في وضع Headed (لرؤية نافذة المتصفح أثناء التطوير)
python run.py --headed

# تخصيص المنفذ
python run.py --port 8000
```

افتح المتصفح وتوجه إلى:
- **Web UI Dashboard**: `http://localhost:8000`
- **Local Mock AI Site**: `http://localhost:8000/mock-site/chat`
- **API Documentation**: `http://localhost:8000/docs`

---

## 🐳 التشغيل بواسطة Docker (Docker & Docker Compose)

```bash
# بناء وتشغيل الحاوية
docker-compose up -d

# متابعة السجلات
docker-compose logs -f
```

---

## 📝 إضافة إعداد موقع جديد (Adding a Site Configuration)

لإضافة موقع جديد، أنشئ ملف YAML داخل مجلد `configs/`، مثلاً `configs/my_portal.yaml`:

```yaml
name: "my_portal"
title: "Custom AI Workspace"
url: "https://example.com/chat"

chat:
  input_selector: "textarea#prompt"
  send_selector: "button[type='submit']"
  input_method: "fill" # أو "type" أو "press_enter"

attachments:
  - name: "document"
    selector: "input#doc-file"
    multiple: false
    description: "PDF/Word Document"
  - name: "image"
    selector: "input#image-file"
    multiple: false
    description: "PNG/JPG Image"

response:
  selector: ".assistant-message.completed"
  generating_selector: ".typing-indicator"
  stop_selector: "button.stop-btn"
  wait_until: "completed"
  timeout: 180
  min_length: 10

auth:
  login_url: "https://example.com/login"
  check_selector: "#user-avatar"
  login_required_selector: "form#login-box"
  auto_pause_for_human: true
```

---

## 🧪 تشغيل الاختبارات الآلية (Testing)

يتضمن المشروع حزمة اختبارات شاملة تغطي:
- إدارة إعدادات YAML وتحقق Pydantic.
- خادم ونقاط الموقع التجريبي المحلي.
- طابور المهام وحالات الـ Job.
- **اختبار End-to-End متكامل**: إطلاق المتصفح، رفع عدة ملفات لحقول مختلفة، إرسال الاستعلام، وانتظار الرد واستخراجه.
- **اختبار Human-in-the-loop**: محاكاة توقف المتصفح عند شاشة تسجيل الدخول واستئناف المهمة بعد موافقة المستخدم.

لتشغيل الاختبارات:

```bash
source .venv/bin/activate
pytest -v
```

---

## 📡 واجهة برمجة التطبيقات (API Reference)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/jobs` | إنشاء مهمة أتمتة جديدة مع ملفات متعددة وتحديد أهدافها |
| `GET` | `/api/jobs` | استرجاع قائمة المهام السابقة وحالاتها |
| `GET` | `/api/jobs/{id}` | جلب تفاصيل مهمة معينة |
| `GET` | `/api/jobs/{id}/logs` | جلب سجلات تنفيذ المهمة |
| `GET` | `/api/jobs/{id}/stream` | بث مباشر لأحداث وحالة المهمة عبر Server-Sent Events (SSE) |
| `POST` | `/api/jobs/{id}/resume` | إشارة استئناف المهمة بعد إكمال تسجيل الدخول البشري / 2FA |
| `POST` | `/api/jobs/{id}/cancel` | إلغاء مهمة قيد الانتظار |
| `GET` | `/api/browser/status` | فحص حالة متصفح Chromium والجلسة الدائمة |
| `POST` | `/api/browser/mode` | التبديل بين وضع Headed و Headless |
| `POST` | `/api/browser/login` | فتح المتصفح تفاعليًا لتسجيل الدخول يدويًا وحفظ الجلسة |
| `GET` | `/api/configs` | جلب كافة إعدادات المواقع المتاحة |
| `POST` | `/api/configs` | حفظ أو تحديث إعداد موقع بصيغة YAML |
| `POST` | `/api/recorder/start` | بدء جلسة متصفح لتسجيل عناصر موقع جديد |
| `POST` | `/api/recorder/generate-config` | استخراج وتوليد ملف YAML من العناصر المسجلة |
