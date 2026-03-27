//go:build helm || unit || unitVersionBump
// +build helm unit unitVersionBump

package unit

import (
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestHelmChartVersionsMatchRelease(t *testing.T) {
	t.Parallel()

	helmChartPath, err := filepath.Abs(chartPath)
	require.NoError(t, err)

	cInfo, err := chartInfo(t, helmChartPath)
	require.NoError(t, err)

	chartAppVersion, exists := cInfo["appVersion"]
	require.True(t, exists, "expected appVersion to exist in chart info")

	chartVersion, exists := cInfo["version"]
	require.True(t, exists, "expected version to exist in chart info")

	expectedAppVersion := "v2.16.2"
	expectedChartVersion := "2.16.2"

	require.Equal(t, expectedAppVersion, chartAppVersion, "appVersion should match release")
	require.Equal(t, expectedChartVersion, chartVersion, "chart version should match release")
}
