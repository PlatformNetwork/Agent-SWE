package byoc_test

import (
	"reflect"
	"testing"

	"github.com/DefangLabs/defang/src/pkg/cli/client"
	defangv1 "github.com/DefangLabs/defang/src/protos/io/defang/v1"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protoreflect"
)

func TestProjectUpdateIncludesEtag(t *testing.T) {
	msg := &defangv1.ProjectUpdate{}
	descriptor := msg.ProtoReflect().Descriptor()
	field := descriptor.Fields().ByName("etag")
	if field == nil {
		t.Fatalf("expected ProjectUpdate to include etag field")
	}
	if field.Kind() != protoreflect.StringKind {
		t.Fatalf("etag field kind = %v, want string", field.Kind())
	}

	value := "etag-value-9x7y"
	msg.ProtoReflect().Set(field, protoreflect.ValueOfString(value))
	encoded, err := proto.Marshal(msg)
	if err != nil {
		t.Fatalf("failed to marshal ProjectUpdate: %v", err)
	}

	var decoded defangv1.ProjectUpdate
	if err := proto.Unmarshal(encoded, &decoded); err != nil {
		t.Fatalf("failed to unmarshal ProjectUpdate: %v", err)
	}
	decodedValue := decoded.ProtoReflect().Get(field).String()
	if decodedValue != value {
		t.Fatalf("etag value roundtrip = %q, want %q", decodedValue, value)
	}
}

func TestPublishMethodRemoved(t *testing.T) {
	fabricType := reflect.TypeOf((*client.FabricClient)(nil)).Elem()
	if _, ok := fabricType.MethodByName("Publish"); ok {
		t.Fatalf("expected FabricClient.Publish to be removed")
	}

	grpcType := reflect.TypeOf(client.GrpcClient{})
	if _, ok := grpcType.MethodByName("Publish"); ok {
		t.Fatalf("expected GrpcClient.Publish to be removed")
	}
}
