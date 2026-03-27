// SPDX-License-Identifier: AGPL-3.0-only

package resourcemanager

import (
    "context"
    "fmt"
    "testing"

    iamv1alpha1 "go.miloapis.com/milo/pkg/apis/iam/v1alpha1"
    resourcemanagerv1alpha1 "go.miloapis.com/milo/pkg/apis/resourcemanager/v1alpha1"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/apimachinery/pkg/runtime"
    "k8s.io/apimachinery/pkg/types"
    ctrl "sigs.k8s.io/controller-runtime"
    "sigs.k8s.io/controller-runtime/pkg/client"
    "sigs.k8s.io/controller-runtime/pkg/client/fake"
)

func TestPersonalOrganizationReconcileCreatesProject(t *testing.T) {
    scheme := runtime.NewScheme()
    if err := iamv1alpha1.AddToScheme(scheme); err != nil {
        t.Fatalf("failed to add iam scheme: %v", err)
    }
    if err := resourcemanagerv1alpha1.AddToScheme(scheme); err != nil {
        t.Fatalf("failed to add resourcemanager scheme: %v", err)
    }

    user := &iamv1alpha1.User{
        ObjectMeta: metav1.ObjectMeta{
            Name: "user-alpha",
            UID:  types.UID("user-alpha-uid-77"),
        },
        Spec: iamv1alpha1.UserSpec{
            GivenName:  "Kira",
            FamilyName: "McMillan",
        },
    }

    fakeClient := fake.NewClientBuilder().WithScheme(scheme).WithObjects(user).Build()

    controller := &PersonalOrganizationController{
        Client: fakeClient,
        Config: PersonalOrganizationControllerConfig{
            RoleName:      "owner",
            RoleNamespace: "roles",
        },
        Scheme: scheme,
    }

    _, err := controller.Reconcile(context.Background(), ctrl.Request{NamespacedName: client.ObjectKey{Name: user.Name}})
    if err != nil {
        t.Fatalf("reconcile failed: %v", err)
    }

    personalOrgName := fmt.Sprintf("personal-org-%s", hashPersonalOrgName(string(user.UID)))
    personalProjectName := fmt.Sprintf("personal-project-%s", hashPersonalOrgName(string(user.UID)))

    org := &resourcemanagerv1alpha1.Organization{}
    if err := fakeClient.Get(context.Background(), client.ObjectKey{Name: personalOrgName}, org); err != nil {
        t.Fatalf("expected organization to exist: %v", err)
    }

    project := &resourcemanagerv1alpha1.Project{}
    if err := fakeClient.Get(context.Background(), client.ObjectKey{Name: personalProjectName}, project); err != nil {
        t.Fatalf("expected project to exist: %v", err)
    }

    displayName := project.Annotations["kubernetes.io/display-name"]
    if displayName != "Personal Project" {
        t.Fatalf("expected display-name annotation to be 'Personal Project', got %q", displayName)
    }

    description := project.Annotations["kubernetes.io/description"]
    expectedDescription := "Kira McMillan's Personal Project"
    if description != expectedDescription {
        t.Fatalf("expected description %q, got %q", expectedDescription, description)
    }

    if project.Spec.OwnerRef.Kind != "Organization" {
        t.Fatalf("expected project owner kind Organization, got %q", project.Spec.OwnerRef.Kind)
    }
    if project.Spec.OwnerRef.Name != org.Name {
        t.Fatalf("expected project owner name %q, got %q", org.Name, project.Spec.OwnerRef.Name)
    }

    if !hasOwnerReference(project.OwnerReferences, user.UID) {
        t.Fatalf("expected project to have owner reference for user %s", user.UID)
    }
}

func TestPersonalOrganizationReconcileUpdatesProjectMetadata(t *testing.T) {
    scheme := runtime.NewScheme()
    if err := iamv1alpha1.AddToScheme(scheme); err != nil {
        t.Fatalf("failed to add iam scheme: %v", err)
    }
    if err := resourcemanagerv1alpha1.AddToScheme(scheme); err != nil {
        t.Fatalf("failed to add resourcemanager scheme: %v", err)
    }

    user := &iamv1alpha1.User{
        ObjectMeta: metav1.ObjectMeta{
            Name: "user-beta",
            UID:  types.UID("user-beta-uid-21"),
        },
        Spec: iamv1alpha1.UserSpec{
            GivenName:  "Aria",
            FamilyName: "Lopez",
        },
    }

    personalOrgName := fmt.Sprintf("personal-org-%s", hashPersonalOrgName(string(user.UID)))
    personalProjectName := fmt.Sprintf("personal-project-%s", hashPersonalOrgName(string(user.UID)))

    existingProject := &resourcemanagerv1alpha1.Project{
        ObjectMeta: metav1.ObjectMeta{
            Name: personalProjectName,
            Annotations: map[string]string{
                "kubernetes.io/display-name": "Old Name",
                "kubernetes.io/description":  "Old description",
            },
            OwnerReferences: []metav1.OwnerReference{
                {
                    Kind: "Organization",
                    Name: "wrong-owner",
                },
            },
        },
        Spec: resourcemanagerv1alpha1.ProjectSpec{
            OwnerRef: resourcemanagerv1alpha1.OwnerReference{
                Kind: "Organization",
                Name: "wrong-owner",
            },
        },
    }

    fakeClient := fake.NewClientBuilder().WithScheme(scheme).WithObjects(user, existingProject).Build()

    controller := &PersonalOrganizationController{
        Client: fakeClient,
        Config: PersonalOrganizationControllerConfig{
            RoleName:      "admin",
            RoleNamespace: "roles",
        },
        Scheme: scheme,
    }

    _, err := controller.Reconcile(context.Background(), ctrl.Request{NamespacedName: client.ObjectKey{Name: user.Name}})
    if err != nil {
        t.Fatalf("reconcile failed: %v", err)
    }

    project := &resourcemanagerv1alpha1.Project{}
    if err := fakeClient.Get(context.Background(), client.ObjectKey{Name: personalProjectName}, project); err != nil {
        t.Fatalf("expected project to exist: %v", err)
    }

    expectedDescription := "Aria Lopez's Personal Project"
    if project.Annotations["kubernetes.io/description"] != expectedDescription {
        t.Fatalf("expected description %q, got %q", expectedDescription, project.Annotations["kubernetes.io/description"])
    }

    if project.Annotations["kubernetes.io/display-name"] != "Personal Project" {
        t.Fatalf("expected display-name to be Personal Project, got %q", project.Annotations["kubernetes.io/display-name"])
    }

    if project.Spec.OwnerRef.Name != personalOrgName {
        t.Fatalf("expected owner ref name %q, got %q", personalOrgName, project.Spec.OwnerRef.Name)
    }
    if project.Spec.OwnerRef.Kind != "Organization" {
        t.Fatalf("expected owner ref kind Organization, got %q", project.Spec.OwnerRef.Kind)
    }

    if !hasOwnerReference(project.OwnerReferences, user.UID) {
        t.Fatalf("expected project to have owner reference for user %s", user.UID)
    }
}

func hasOwnerReference(references []metav1.OwnerReference, uid types.UID) bool {
    for _, reference := range references {
        if reference.UID == uid {
            return true
        }
    }
    return false
}
