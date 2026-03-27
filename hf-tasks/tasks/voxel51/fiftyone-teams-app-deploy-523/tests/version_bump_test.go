//go:build docker || compose || unit || unitComposeVersionBump
// +build docker compose unit unitComposeVersionBump

package unit

import (
	"context"
	"testing"

	"github.com/compose-spec/compose-go/v2/cli"
	"github.com/stretchr/testify/require"
)

func TestInternalAuthComposeUsesReleaseImages(t *testing.T) {
	t.Parallel()

	projectOptions, err := cli.NewProjectOptions(
		[]string{internalAuthComposeFile},
		cli.WithWorkingDirectory(dockerInternalAuthDir),
		cli.WithName("fiftyone-compose-test"),
		cli.WithEnvFiles(internalAuthEnvTemplateFilePath, envFixtureFilePath),
		cli.WithDotEnv,
	)
	require.NoError(t, err)

	project, err := cli.ProjectFromOptions(context.TODO(), projectOptions)
	require.NoError(t, err)

	expectedTag := "v2.16.2"
	require.Equal(t, "voxel51/fiftyone-app:"+expectedTag, project.Services["fiftyone-app"].Image)
	require.Equal(t, "voxel51/fiftyone-teams-api:"+expectedTag, project.Services["teams-api"].Image)
	require.Equal(t, "voxel51/fiftyone-teams-app:"+expectedTag, project.Services["teams-app"].Image)
	require.Equal(t, "voxel51/fiftyone-teams-cas:"+expectedTag, project.Services["teams-cas"].Image)
}

func TestInternalAuthComposeSetsSdkRecommendedVersion(t *testing.T) {
	t.Parallel()

	projectOptions, err := cli.NewProjectOptions(
		[]string{internalAuthComposeFile},
		cli.WithWorkingDirectory(dockerInternalAuthDir),
		cli.WithName("fiftyone-compose-test"),
		cli.WithEnvFiles(internalAuthEnvTemplateFilePath, envFixtureFilePath),
		cli.WithDotEnv,
	)
	require.NoError(t, err)

	project, err := cli.ProjectFromOptions(context.TODO(), projectOptions)
	require.NoError(t, err)

	expectedVersion := "2.16.2"
	env := project.Services["teams-app"].Environment
	require.Equal(t, &expectedVersion, env["FIFTYONE_APP_TEAMS_SDK_RECOMMENDED_VERSION"], "recommended SDK version should match release")
}

func TestLegacyAuthComposeUsesReleaseImages(t *testing.T) {
	t.Parallel()

	projectOptions, err := cli.NewProjectOptions(
		[]string{legacyAuthComposeFile},
		cli.WithWorkingDirectory(dockerLegacyAuthDir),
		cli.WithName("fiftyone-compose-test"),
		cli.WithEnvFiles(legacyAuthEnvTemplateFilePath, envFixtureFilePath),
		cli.WithDotEnv,
	)
	require.NoError(t, err)

	project, err := cli.ProjectFromOptions(context.TODO(), projectOptions)
	require.NoError(t, err)

	expectedTag := "v2.16.2"
	require.Equal(t, "voxel51/fiftyone-app:"+expectedTag, project.Services["fiftyone-app"].Image)
	require.Equal(t, "voxel51/fiftyone-teams-api:"+expectedTag, project.Services["teams-api"].Image)
	require.Equal(t, "voxel51/fiftyone-teams-app:"+expectedTag, project.Services["teams-app"].Image)
	require.Equal(t, "voxel51/fiftyone-teams-cas:"+expectedTag, project.Services["teams-cas"].Image)
}

func TestLegacyAuthComposeSetsSdkRecommendedVersion(t *testing.T) {
	t.Parallel()

	projectOptions, err := cli.NewProjectOptions(
		[]string{legacyAuthComposeFile},
		cli.WithWorkingDirectory(dockerLegacyAuthDir),
		cli.WithName("fiftyone-compose-test"),
		cli.WithEnvFiles(legacyAuthEnvTemplateFilePath, envFixtureFilePath),
		cli.WithDotEnv,
	)
	require.NoError(t, err)

	project, err := cli.ProjectFromOptions(context.TODO(), projectOptions)
	require.NoError(t, err)

	expectedVersion := "2.16.2"
	env := project.Services["teams-app"].Environment
	require.Equal(t, &expectedVersion, env["FIFTYONE_APP_TEAMS_SDK_RECOMMENDED_VERSION"], "recommended SDK version should match release")
}
