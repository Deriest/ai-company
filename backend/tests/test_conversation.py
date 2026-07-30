"""AIC Platform — Conversation Engine Tests.

Tests intent detection and task creation from natural language.
"""
import pytest
from conversation.engine import ConversationEngine


class TestIntentDetection:
    def _detect(self, content):
        # We need a session for ConversationEngine, but _detect_intent is pure
        engine = ConversationEngine.__new__(ConversationEngine)
        return engine._detect_intent(content)

    def test_task_request_build(self):
        assert self._detect("Build a landing page") == "task_request"

    def test_task_request_fix(self):
        assert self._detect("Fix the authentication bug") == "task_request"

    def test_task_request_create(self):
        assert self._detect("Create a new API endpoint") == "task_request"

    def test_status_request(self):
        assert self._detect("What is the progress?") == "status"

    def test_status_request_progress(self):
        assert self._detect("Show me the progress") == "status"

    def test_question_what(self):
        assert self._detect("What can you do?") == "question"

    def test_question_how(self):
        assert self._detect("How does this work?") == "question"

    def test_question_with_action_word(self):
        # "How do I create a task?" is a question, not a task request
        assert self._detect("How do I create a task?") == "question"

    def test_approval_approve(self):
        assert self._detect("Approve the last task") == "approval"

    def test_approval_reject(self):
        assert self._detect("Reject the deployment") == "approval"

    def test_chat_general(self):
        assert self._detect("hello") == "chat"

    def test_question_ends_with_mark(self):
        assert self._detect("Is it ready?") == "question"

    def test_force_phrase_still_task_request(self):
        # force phrases are task_request; creation force is separate method
        assert self._detect("Create a login page with JWT auth for users") == "task_request"


class TestForceTaskCreation:
    def _force(self, content):
        engine = ConversationEngine.__new__(ConversationEngine)
        return engine._user_forces_task_creation(content)

    def test_build_now(self):
        assert self._force("build now") is True

    def test_create_the_task(self):
        assert self._force("please create the task") is True

    def test_normal_request_not_forced(self):
        assert self._force("Build a landing page for our marketing site") is False

    def test_indonesian_force(self):
        assert self._force("kerjakan sekarang") is True


class TestTaskClassification:
    def _classify(self, content):
        engine = ConversationEngine.__new__(ConversationEngine)
        return engine._classify_task(content)

    def test_bugfix(self):
        task_type, worker = self._classify("Fix the login bug")
        assert task_type == "bugfix"
        assert worker == "backend"

    def test_feature(self):
        task_type, worker = self._classify("Build a dashboard")
        assert task_type == "feature"
        assert worker == "frontend"

    def test_docs(self):
        task_type, worker = self._classify("Write documentation for the API")
        assert task_type == "docs"

    def test_test(self):
        task_type, worker = self._classify("Add unit tests for auth module")
        assert task_type == "test"
        assert worker == "qa"

    def test_infra(self):
        task_type, worker = self._classify("Deploy to production server")
        assert task_type == "infra"
        assert worker == "devops"

    def test_refactor(self):
        task_type, worker = self._classify("Refactor the database layer")
        assert task_type == "refactor"


class TestTitleExtraction:
    def _extract(self, content):
        engine = ConversationEngine.__new__(ConversationEngine)
        return engine._extract_title(content)

    def test_build_prefix(self):
        title = self._extract("Build a landing page for OKN website")
        assert len(title) > 0

    def test_fix_prefix(self):
        title = self._extract("Fix authentication bug")
        assert title.startswith("Authentication") or title.startswith("Fix")

    def test_create_prefix(self):
        title = self._extract("Create a new API endpoint")
        assert len(title) > 0

    def test_empty_content(self):
        title = self._extract("")
        assert title == ""
