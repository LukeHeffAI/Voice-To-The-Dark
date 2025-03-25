# Voice To The Dark – Project Plan

**Voice To The Dark** is a web application that extracts horror stories from the NoSleep subreddit and narrates them using the ElevenLabs API. This document outlines the modular task breakdown for the project.

---

## ✅ 1. Planning and Requirements

- [ ] Define project scope and key goals.
  - URL input, story extraction, narration, secure access.
- [ ] Design user workflow and wireframes.
- [ ] Outline security architecture.
  - E.g., access control via login/invite.
- [ ] Select tech stack.
  - Frontend: React/Vue or HTML/CSS/JS.
  - Backend: Python (Flask/Django) or Node.js.
  - ElevenLabs API, hosting provider.

---

## ⚙️ 2. Environment Setup

- [ ] Set up Git repository and version control.
- [ ] Configure local development environment.
- [ ] Store API keys securely (e.g., `.env`).
- [ ] Define folder structure and config files.

---

## 🎨 3. Module 1: Frontend Development

- [ ] Build user interface:
  - Input field for NoSleep URLs.
- [ ] Implement input validation:
  - Check if URL is from r/NoSleep and valid format.
- [ ] Create responsive UI for desktop/mobile.
- [ ] Add user feedback:
  - Loading indicators, error messages.

---

## 🧠 4. Module 2: Backend Development

- [ ] Create URL submission API endpoint.
- [ ] Build content extraction logic:
  - Parse NoSleep HTML (BeautifulSoup or Cheerio).
- [ ] Handle layout variations (e.g., reposts, markdown).
- [ ] Implement error handling:
  - Story not found, parsing failed, etc.

---

## 🗣️ 5. Module 3: ElevenLabs API Integration

- [ ] Set up API call to ElevenLabs:
  - Send extracted text and receive audio.
- [ ] Handle long stories:
  - Chunk text if needed.
- [ ] Save and serve generated audio file.
- [ ] Secure backend access to API.

---

## 🔐 6. Module 4: Security and Access Control

- [ ] Add user authentication:
  - Basic auth, OAuth, or invite-only system.
- [ ] Protect backend routes:
  - Middleware to restrict unauthorized use.
- [ ] Secure hosting:
  - HTTPS, firewalls, rate limiting.
- [ ] Sanitize user input.

---

## 🚀 7. Module 5: Deployment and Hosting

- [ ] Configure custom domain and DNS.
- [ ] Deploy backend/frontend (e.g., Render, DigitalOcean, Vercel).
- [ ] Set up HTTPS with SSL/TLS certs.
- [ ] Set up CI/CD (GitHub Actions, Railway deploys).

---

## 🧪 8. Module 6: Testing and Quality Assurance

- [ ] Write unit tests:
  - Text extraction, API calls, authentication logic.
- [ ] Perform integration testing:
  - Frontend ↔ Backend ↔ ElevenLabs.
- [ ] Conduct end-to-end testing.
- [ ] Perform security and vulnerability tests.

---

## 🧾 9. Module 7: Documentation and Maintenance

- [ ] Write technical documentation:
  - Code structure, APIs, deployment steps.
- [ ] Create user-facing help:
  - FAQs, usage guide.
- [ ] Add logging and error tracking.
- [ ] Plan for regular maintenance, updates, and security checks.

---

### 📌 Note:
When beginning a new phase, we will:
1. Refer back to the tasks in the corresponding module above.
2. Review and finalize details together.
3. Begin implementation with full clarity.
