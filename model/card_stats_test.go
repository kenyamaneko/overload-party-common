package model

import (
	"encoding/json"
	"testing"
)

// --- IsComputeType ---

func TestIsComputeType(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"Compute", true},
		{"Container", true},
		{"Orchestrator", true},
		{"Serverless", true},
		{"AI/ML", false}, // AI/ML is now separate
		{"Database", false},
		{"ObjectStorage", false},
		{"Platform", false},
		{"Strategy", false},
		{"", false},
	}
	for _, tt := range tests {
		if got := IsComputeType(tt.cardType); got != tt.want {
			t.Errorf("IsComputeType(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

// --- IsAIMLType ---

func TestIsAIMLType(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"AI/ML", true},
		{"Compute", false},
		{"Container", false},
		{"Orchestrator", false},
		{"Serverless", false},
		{"Database", false},
		{"Platform", false},
		{"", false},
	}
	for _, tt := range tests {
		if got := IsAIMLType(tt.cardType); got != tt.want {
			t.Errorf("IsAIMLType(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

// --- IsDBType ---

func TestIsDBType(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"Database", true},
		{"NoSQL", false}, // NoSQL merged into Database
		{"CacheDB", true},
		{"ObjectStorage", false}, // ObjectStorage, not DB type
		{"Compute", false},
		{"Platform", false},
		{"", false},
	}
	for _, tt := range tests {
		if got := IsDBType(tt.cardType); got != tt.want {
			t.Errorf("IsDBType(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

// --- IsStorageType ---

func TestIsStorageType(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"ObjectStorage", true},
		{"Database", false},
		{"NoSQL", false},
		{"CacheDB", false},
		{"Compute", false},
		{"Platform", false},
		{"", false},
	}
	for _, tt := range tests {
		if got := IsStorageType(tt.cardType); got != tt.want {
			t.Errorf("IsStorageType(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

// --- IsDataType ---

func TestIsDataType(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"Database", true},
		{"ObjectStorage", true},
		{"NoSQL", false}, // NoSQL merged into Database
		{"CacheDB", true},
		{"Compute", false},
		{"Platform", false},
		{"", false},
	}
	for _, tt := range tests {
		if got := IsDataType(tt.cardType); got != tt.want {
			t.Errorf("IsDataType(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

// --- IsResourceType ---

func TestIsResourceType(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"Compute", true},
		{"Database", true},
		{"ObjectStorage", true},
		{"AI/ML", true},
		{"Platform", false},
		{"Attachment", false},
		{"Strategy", false},
		{"Incident", false},
	}
	for _, tt := range tests {
		if got := IsResourceType(tt.cardType); got != tt.want {
			t.Errorf("IsResourceType(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

// --- Zone Eligibility ---

func TestIsFrontendEligible(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"Compute", true},
		{"Container", true},
		{"Orchestrator", true},
		{"Serverless", true},
		{"AI/ML", true},
		{"ObjectStorage", true}, // special: can be placed as wall (no DV gen, no attack)
		{"Database", false},
		{"NoSQL", false},
		{"CacheDB", false},
		{"Platform", false},
	}
	for _, tt := range tests {
		if got := IsFrontendEligible(tt.cardType); got != tt.want {
			t.Errorf("IsFrontendEligible(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

func TestIsBackendEligible(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"Database", true},
		{"NoSQL", false}, // NoSQL merged into Database
		{"CacheDB", true},
		{"ObjectStorage", true},
		{"Compute", true}, // compute in backend can monetize DV
		{"Container", true},
		{"Orchestrator", true},
		{"Serverless", true},
		{"AI/ML", true},
		{"Platform", false},
		{"Strategy", false},
	}
	for _, tt := range tests {
		if got := IsBackendEligible(tt.cardType); got != tt.want {
			t.Errorf("IsBackendEligible(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

// --- IsSupportType ---

func TestIsSupportType(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"Platform", true},
		{"Attachment", false}, // Attachments attach to resources, not support zone
		{"Strategy", true},
		{"Incident", true},
		{"Reactive", true},
		{"Compute", false},
		{"Database", false},
	}
	for _, tt := range tests {
		if got := IsSupportType(tt.cardType); got != tt.want {
			t.Errorf("IsSupportType(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

func TestIsAttachmentType(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"Attachment", true},
		{"Platform", false},
		{"Compute", false},
	}
	for _, tt := range tests {
		if got := IsAttachmentType(tt.cardType); got != tt.want {
			t.Errorf("IsAttachmentType(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

// --- IsImmediateType ---

func TestIsImmediateType(t *testing.T) {
	tests := []struct {
		cardType string
		want     bool
	}{
		{"Strategy", true},
		{"Incident", true},
		{"Platform", false},
		{"Reactive", false},
		{"Compute", false},
	}
	for _, tt := range tests {
		if got := IsImmediateType(tt.cardType); got != tt.want {
			t.Errorf("IsImmediateType(%q) = %v, want %v", tt.cardType, got, tt.want)
		}
	}
}

// --- ParseComputeStats ---

func TestParseComputeStats(t *testing.T) {
	raw := json.RawMessage(`{"throughput": 700, "availability": 1400, "maintenance_cost": 200, "deploy_cost": 400, "sla_penalty": 400}`)
	stats, err := ParseComputeStats(raw)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if stats.Throughput != 700 {
		t.Errorf("throughput = %d, want 700", stats.Throughput)
	}
	if stats.Availability != 1400 {
		t.Errorf("availability = %d, want 1400", stats.Availability)
	}
	if stats.MaintenanceCost != 200 {
		t.Errorf("maintenance_cost = %d, want 200", stats.MaintenanceCost)
	}
	if stats.SLAPenalty != 400 {
		t.Errorf("sla_penalty = %d, want 400", stats.SLAPenalty)
	}
	if stats.ThroughputMax != nil {
		t.Errorf("throughput_max should be nil")
	}
}

func TestParseComputeStats_WithMax(t *testing.T) {
	raw := json.RawMessage(`{"throughput": 500, "throughput_max": 1200, "availability": 1000, "maintenance_cost": 100, "deploy_cost": 300, "sla_penalty": 300}`)
	stats, err := ParseComputeStats(raw)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if stats.ThroughputMax == nil || *stats.ThroughputMax != 1200 {
		t.Errorf("throughput_max = %v, want 1200", stats.ThroughputMax)
	}
}

func TestParseComputeStats_InvalidJSON(t *testing.T) {
	raw := json.RawMessage(`{invalid}`)
	_, err := ParseComputeStats(raw)
	if err == nil {
		t.Fatal("expected error for invalid JSON")
	}
}

// --- ParseDataStats (Yield) ---

func TestParseDataStats(t *testing.T) {
	raw := json.RawMessage(`{"yield": 500, "availability": 1300, "deploy_cost": 400, "sla_penalty": 500}`)
	stats, err := ParseDataStats(raw)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if stats.Yield != 500 {
		t.Errorf("yield = %d, want 500", stats.Yield)
	}
	if stats.Availability != 1300 {
		t.Errorf("availability = %d, want 1300", stats.Availability)
	}
	if stats.SLAPenalty != 500 {
		t.Errorf("sla_penalty = %d, want 500", stats.SLAPenalty)
	}
	if stats.YieldMax != nil {
		t.Errorf("yield_max should be nil")
	}
}

func TestParseDataStats_InvalidJSON(t *testing.T) {
	raw := json.RawMessage(`not json`)
	_, err := ParseDataStats(raw)
	if err == nil {
		t.Fatal("expected error for invalid JSON")
	}
}

