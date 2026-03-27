//go:build small

package api //nolint:revive

import (
    "net/http"
    "net/http/httptest"
    "strings"
    "testing"

    "github.com/stretchr/testify/assert"
    "github.com/web-platform-tests/wpt.fyi/shared/sharedtest"
    "go.uber.org/mock/gomock"
)

func TestHandleMetadataTriage_InvalidURLMissingScheme(t *testing.T) {
    mockCtrl := gomock.NewController(t)
    defer mockCtrl.Finish()
    ctx := sharedtest.NewTestContext()
    w := httptest.NewRecorder()

    body :=
        `{
        "/baz/qux.html": [
            {
                "product":"firefox",
                "url":"issues.example.com/12345",
                "results":[{"status":6}]
            }
        ]}`
    bodyReader := strings.NewReader(body)
    req := httptest.NewRequest("PATCH", "https://foo/metadata", bodyReader)
    req.Header.Set("Content-Type", "application/json")

    mockgac := sharedtest.NewMockGitHubAccessControl(mockCtrl)
    mockgac.EXPECT().IsValidWPTMember().Return(true, nil)

    mocktm := sharedtest.NewMockTriageMetadata(mockCtrl)
    mocktm.EXPECT().Triage(gomock.Any()).Times(0)

    mockCache := sharedtest.NewMockObjectCache(mockCtrl)
    mockCache.EXPECT().Put(gomock.Any(), gomock.Any()).Times(0)

    mockSet := sharedtest.NewMockRedisSet(mockCtrl)
    mockSet.EXPECT().Add(gomock.Any(), gomock.Any()).Times(0)

    handleMetadataTriage(ctx, mockgac, mocktm, mockCache, mockSet, w, req)

    assert.Equal(t, http.StatusBadRequest, w.Code)
    assert.Contains(t, w.Body.String(), "Invalid URL")
}

func TestHandleMetadataTriage_InvalidURLMalformedHost(t *testing.T) {
    mockCtrl := gomock.NewController(t)
    defer mockCtrl.Finish()
    ctx := sharedtest.NewTestContext()
    w := httptest.NewRecorder()

    body :=
        `{
        "/baz/quux.html": [
            {
                "product":"chrome",
                "url":"http://bad host.example/issue",
                "results":[{"status":6}]
            }
        ]}`
    bodyReader := strings.NewReader(body)
    req := httptest.NewRequest("PATCH", "https://foo/metadata", bodyReader)
    req.Header.Set("Content-Type", "application/json")

    mockgac := sharedtest.NewMockGitHubAccessControl(mockCtrl)
    mockgac.EXPECT().IsValidWPTMember().Return(true, nil)

    mocktm := sharedtest.NewMockTriageMetadata(mockCtrl)
    mocktm.EXPECT().Triage(gomock.Any()).Times(0)

    mockCache := sharedtest.NewMockObjectCache(mockCtrl)
    mockCache.EXPECT().Put(gomock.Any(), gomock.Any()).Times(0)

    mockSet := sharedtest.NewMockRedisSet(mockCtrl)
    mockSet.EXPECT().Add(gomock.Any(), gomock.Any()).Times(0)

    handleMetadataTriage(ctx, mockgac, mocktm, mockCache, mockSet, w, req)

    assert.Equal(t, http.StatusBadRequest, w.Code)
    assert.Contains(t, w.Body.String(), "Invalid URL")
}

func TestHandleMetadataTriage_InvalidURLMixedLinks(t *testing.T) {
    mockCtrl := gomock.NewController(t)
    defer mockCtrl.Finish()
    ctx := sharedtest.NewTestContext()
    w := httptest.NewRecorder()

    body :=
        `{
        "/baz/mixed.html": [
            {
                "product":"edge",
                "url":"https://valid.example/issue/9",
                "results":[{"status":6}]
            },
            {
                "product":"edge",
                "url":"https://",
                "results":[{"status":6}]
            }
        ]}`
    bodyReader := strings.NewReader(body)
    req := httptest.NewRequest("PATCH", "https://foo/metadata", bodyReader)
    req.Header.Set("Content-Type", "application/json")

    mockgac := sharedtest.NewMockGitHubAccessControl(mockCtrl)
    mockgac.EXPECT().IsValidWPTMember().Return(true, nil)

    mocktm := sharedtest.NewMockTriageMetadata(mockCtrl)
    mocktm.EXPECT().Triage(gomock.Any()).Times(0)

    mockCache := sharedtest.NewMockObjectCache(mockCtrl)
    mockCache.EXPECT().Put(gomock.Any(), gomock.Any()).Times(0)

    mockSet := sharedtest.NewMockRedisSet(mockCtrl)
    mockSet.EXPECT().Add(gomock.Any(), gomock.Any()).Times(0)

    handleMetadataTriage(ctx, mockgac, mocktm, mockCache, mockSet, w, req)

    assert.Equal(t, http.StatusBadRequest, w.Code)
    assert.Contains(t, w.Body.String(), "Invalid URL")
    assert.Contains(t, w.Body.String(), "https://")
    assert.NotContains(t, w.Body.String(), "valid.example")
}
