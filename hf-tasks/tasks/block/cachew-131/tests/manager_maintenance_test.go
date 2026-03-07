package gitclone

import (
	"context"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/block/cachew/internal/logging"
)

func setupFakeGit(t *testing.T) (logFile string, restore func()) {
	t.Helper()

	tmpDir := t.TempDir()
	logFile = filepath.Join(tmpDir, "git.log")

	scriptPath := filepath.Join(tmpDir, "git")
	script := "#!/bin/sh\n" +
		"if [ -n \"$GIT_LOG\" ]; then\n" +
		"  printf '%s\\n' \"$*\" >> \"$GIT_LOG\"\n" +
		"fi\n" +
		"if [ \"$1\" = \"-C\" ]; then\n" +
		"  shift 2\n" +
		"fi\n" +
		"cmd=\"$1\"\n" +
		"if [ \"$cmd\" = \"clone\" ]; then\n" +
		"  last=\"\"\n" +
		"  for arg in \"$@\"; do\n" +
		"    last=\"$arg\"\n" +
		"  done\n" +
		"  if [ -n \"$last\" ]; then\n" +
		"    mkdir -p \"$last\"\n" +
		"    touch \"$last/HEAD\"\n" +
		"  fi\n" +
		"fi\n" +
		"exit 0\n"

	if err := os.WriteFile(scriptPath, []byte(script), 0o755); err != nil {
		t.Fatalf("write fake git: %v", err)
	}

	oldPath := os.Getenv("PATH")
	oldLog := os.Getenv("GIT_LOG")
	if err := os.Setenv("PATH", tmpDir+string(os.PathListSeparator)+oldPath); err != nil {
		t.Fatalf("set PATH: %v", err)
	}
	if err := os.Setenv("GIT_LOG", logFile); err != nil {
		t.Fatalf("set GIT_LOG: %v", err)
	}

	restore = func() {
		_ = os.Setenv("PATH", oldPath)
		_ = os.Setenv("GIT_LOG", oldLog)
	}

	return logFile, restore
}

func logLines(t *testing.T, logFile string) []string {
	t.Helper()

	data, err := os.ReadFile(logFile)
	if err != nil {
		t.Fatalf("read git log: %v", err)
	}
	trimmed := strings.TrimSpace(string(data))
	if trimmed == "" {
		return []string{}
	}
	return strings.Split(trimmed, "\n")
}

func containsLine(lines []string, substr string) bool {
	for _, line := range lines {
		if strings.Contains(line, substr) {
			return true
		}
	}
	return false
}

func testContext(t *testing.T) context.Context {
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	return logging.ContextWithLogger(context.Background(), logger)
}

func TestManagerStartsMaintenanceOnNewManager(t *testing.T) {
	logFile, restore := setupFakeGit(t)
	defer restore()

	ctx := testContext(t)

	config := Config{
		MirrorRoot:  t.TempDir(),
		Maintenance: true,
	}

	_, err := NewManager(ctx, config, nil)
	if err != nil {
		t.Fatalf("new manager: %v", err)
	}

	lines := logLines(t, logFile)
	if len(lines) == 0 {
		t.Fatalf("expected git commands to run, log was empty")
	}
	if !containsLine(lines, "maintenance start") {
		t.Fatalf("expected maintenance start call, got logs: %v", lines)
	}
}

func TestRegisterMaintenanceOnCloneAndDiscover(t *testing.T) {
	logFile, restore := setupFakeGit(t)
	defer restore()

	ctx := testContext(t)
	mirrorRoot := t.TempDir()

	config := Config{
		MirrorRoot:  mirrorRoot,
		Maintenance: true,
	}

	manager, err := NewManager(ctx, config, nil)
	if err != nil {
		t.Fatalf("new manager: %v", err)
	}

	repo, err := manager.GetOrCreate(ctx, "https://example.com/mirror/one")
	if err != nil {
		t.Fatalf("get or create: %v", err)
	}
	if err := repo.Clone(ctx); err != nil {
		t.Fatalf("clone: %v", err)
	}

	discoverPath := filepath.Join(mirrorRoot, "example.org", "mirror", "two")
	if err := os.MkdirAll(discoverPath, 0o755); err != nil {
		t.Fatalf("create discover path: %v", err)
	}
	if err := os.WriteFile(filepath.Join(discoverPath, "HEAD"), []byte("ref: refs/heads/main\n"), 0o644); err != nil {
		t.Fatalf("write HEAD: %v", err)
	}

	if _, err := manager.DiscoverExisting(ctx); err != nil {
		t.Fatalf("discover existing: %v", err)
	}

	lines := logLines(t, logFile)
	if len(lines) == 0 {
		t.Fatalf("expected git commands to run, log was empty")
	}
	if !containsLine(lines, "maintenance register") {
		t.Fatalf("expected maintenance register call, got logs: %v", lines)
	}
	if !containsLine(lines, "maintenance.strategy incremental") {
		t.Fatalf("expected maintenance.strategy incremental, got logs: %v", lines)
	}
	if !containsLine(lines, "config protocol.version 2") {
		t.Fatalf("expected mirror config commands, got logs: %v", lines)
	}
}
