const { createApp } = Vue;

const API_BASE = "/api/v1";

createApp({
  data() {
    return {
      activePanel: "auth",
      token: localStorage.getItem("access_token") || "",
      refreshToken: localStorage.getItem("refresh_token") || "",
      currentUser: null,
      resumes: [],
      selectedResume: null,
      chunks: [],
      searchResults: [],
      providerName: "mock",
      lastCode: "",
      notice: { type: "info", text: "" },
      auth: {
        registerEmail: "",
        registerPassword: "",
        fullName: "",
        loginEmail: "",
        loginPassword: "",
        code: "",
      },
      rag: {
        query: "Redis 验证码怎么做",
        topK: 5,
      },
      interview: {
        focus: "FastAPI Redis RAG",
        questionCount: 3,
        topK: 5,
        questions: [],
        currentQuestion: "",
        answer: "",
        scoreResult: null,
        followUp: null,
      },
    };
  },
  computed: {
    navItems() {
      return [
        { id: "auth", index: "01", label: "账号" },
        { id: "resumes", index: "02", label: "简历" },
        { id: "rag", index: "03", label: "RAG" },
        { id: "interview", index: "04", label: "面试" },
      ];
    },
    visibleChunks() {
      return this.searchResults.length ? this.searchResults : this.chunks;
    },
  },
  async mounted() {
    if (this.token) {
      await this.fetchMe({ silent: true });
      await this.loadResumes({ silent: true });
    }
  },
  methods: {
    async api(path, options = {}) {
      const headers = { ...(options.headers || {}) };
      if (options.json) {
        headers["Content-Type"] = "application/json";
      }
      if (options.auth !== false && this.token) {
        headers.Authorization = `Bearer ${this.token}`;
      }

      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
        body: options.json ? JSON.stringify(options.json) : options.body,
      });
      const text = await response.text();
      const data = text ? JSON.parse(text) : null;
      if (!response.ok) {
        throw new Error(data?.detail || `HTTP ${response.status}`);
      }
      return data;
    },
    setNotice(text, type = "info") {
      this.notice = { type, text };
    },
    async register() {
      try {
        await this.api("/auth/register", {
          method: "POST",
          auth: false,
          json: {
            email: this.auth.registerEmail,
            password: this.auth.registerPassword,
            full_name: this.auth.fullName || null,
          },
        });
        this.auth.loginEmail = this.auth.registerEmail;
        this.auth.loginPassword = this.auth.registerPassword;
        this.setNotice("注册成功，可以发送验证码登录", "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async sendCode() {
      try {
        const email = this.auth.loginEmail || this.auth.registerEmail;
        const data = await this.api("/verification/send", {
          method: "POST",
          auth: false,
          json: { email },
        });
        this.lastCode = data.codes;
        this.auth.code = data.codes;
        this.setNotice(`验证码已生成，有效期 ${data.expires_in_seconds} 秒`, "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async login() {
      try {
        const data = await this.api("/auth/login", {
          method: "POST",
          auth: false,
          json: {
            email: this.auth.loginEmail,
            password: this.auth.loginPassword,
            code: this.auth.code,
          },
        });
        this.token = data.access_token;
        this.refreshToken = data.refresh_token;
        localStorage.setItem("access_token", this.token);
        localStorage.setItem("refresh_token", this.refreshToken);
        await this.fetchMe({ silent: true });
        await this.loadResumes({ silent: true });
        this.activePanel = "resumes";
        this.setNotice("登录成功", "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async logout() {
      if (this.refreshToken) {
        try {
          await this.api("/auth/logout", {
            method: "POST",
            auth: false,
            json: { refresh_token: this.refreshToken },
          });
        } catch {
          // Local state is cleared even if the refresh token has already expired.
        }
      }
      this.token = "";
      this.refreshToken = "";
      this.currentUser = null;
      this.resumes = [];
      this.selectedResume = null;
      this.chunks = [];
      this.searchResults = [];
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      this.activePanel = "auth";
      this.setNotice("已退出", "info");
    },
    async fetchMe(options = {}) {
      try {
        this.currentUser = await this.api("/auth/me");
        if (!options.silent) this.setNotice("当前用户已刷新", "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async loadResumes(options = {}) {
      try {
        this.resumes = await this.api("/resumes");
        if (!this.selectedResume && this.resumes.length) {
          await this.selectResume(this.resumes[0], { silent: true });
        }
        if (!options.silent) this.setNotice("简历列表已刷新", "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async uploadResume() {
      const file = this.$refs.fileInput.files[0];
      if (!file) return;
      const body = new FormData();
      body.append("file", file);
      try {
        const resume = await this.api("/resumes", {
          method: "POST",
          body,
        });
        await this.loadResumes({ silent: true });
        await this.selectResume(resume, { silent: true });
        this.activePanel = "rag";
        this.setNotice(`简历 #${resume.id} 上传成功`, "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async selectResume(resume, options = {}) {
      this.selectedResume = resume;
      this.searchResults = [];
      this.interview.questions = [];
      this.interview.scoreResult = null;
      this.interview.followUp = null;
      await this.loadChunks({ silent: true });
      if (!options.silent) this.setNotice(`已选择简历 #${resume.id}`, "success");
    },
    async buildChunks() {
      if (!this.selectedResume) return;
      try {
        const data = await this.api(`/resumes/${this.selectedResume.id}/chunks`, {
          method: "POST",
        });
        await this.loadChunks({ silent: true });
        this.setNotice(`已构建 ${data.chunks_created} 个 chunks`, "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async loadChunks(options = {}) {
      if (!this.selectedResume) return;
      try {
        this.chunks = await this.api(`/resumes/${this.selectedResume.id}/chunks`);
        if (!options.silent) this.setNotice("chunks 已刷新", "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async searchChunks() {
      if (!this.selectedResume) return;
      try {
        this.searchResults = await this.api(`/resumes/${this.selectedResume.id}/search`, {
          method: "POST",
          json: {
            query: this.rag.query,
            top_k: this.rag.topK,
          },
        });
        this.setNotice(`检索返回 ${this.searchResults.length} 个结果`, "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async generateQuestions() {
      if (!this.selectedResume) return;
      try {
        const data = await this.api(`/resumes/${this.selectedResume.id}/interview/questions`, {
          method: "POST",
          json: {
            focus: this.interview.focus,
            question_count: this.interview.questionCount,
            top_k: this.interview.topK,
          },
        });
        this.providerName = data.provider;
        this.interview.questions = data.questions;
        if (data.questions.length) {
          this.useQuestion(data.questions[0].question);
        }
        this.setNotice(`已生成 ${data.questions.length} 道题`, "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    useQuestion(question) {
      this.interview.currentQuestion = question;
    },
    async scoreAnswer() {
      if (!this.selectedResume) return;
      try {
        const data = await this.api(`/resumes/${this.selectedResume.id}/interview/score`, {
          method: "POST",
          json: {
            question: this.interview.currentQuestion,
            answer: this.interview.answer,
            top_k: this.interview.topK,
          },
        });
        this.providerName = data.provider;
        this.interview.scoreResult = data;
        this.setNotice(`评分完成：${data.score}`, "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    async generateFollowUp() {
      if (!this.selectedResume) return;
      try {
        const data = await this.api(`/resumes/${this.selectedResume.id}/interview/follow-up`, {
          method: "POST",
          json: {
            question: this.interview.currentQuestion,
            answer: this.interview.answer,
            top_k: this.interview.topK,
          },
        });
        this.providerName = data.provider;
        this.interview.followUp = data;
        this.setNotice("追问已生成", "success");
      } catch (error) {
        this.setNotice(error.message, "error");
      }
    },
    formatDate(value) {
      if (!value) return "-";
      return new Date(value).toLocaleString("zh-CN", { hour12: false });
    },
  },
}).mount("#app");
