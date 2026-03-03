package model

import (
	"encoding/json"
	"testing"
)

func newTestGameState() *GameState {
	emptyField, _ := json.Marshal(&Field{})
	emptyHand, _ := json.Marshal([]HandCard{})
	emptyRepo, _ := json.Marshal([]int64{10, 20, 30})
	emptyTrash, _ := json.Marshal([]int64{})

	return &GameState{
		GameID:            "test-helpers",
		Version:           1,
		Player1Budget:     5000,
		Player1InsightPool:     500,
		Player1Field:      emptyField,
		Player1Hand:       emptyHand,
		Player1Repository: emptyRepo,
		Player1Trash:      emptyTrash,
		Player1TimeBank:   480,
		Player2Budget:     4000,
		Player2InsightPool:     300,
		Player2Field:      emptyField,
		Player2Hand:       emptyHand,
		Player2Repository: emptyRepo,
		Player2Trash:      emptyTrash,
		Player2TimeBank:   360,
	}
}

// --- Budget ---

func TestGetSetBudget(t *testing.T) {
	gs := newTestGameState()

	if gs.GetBudget(1) != 5000 {
		t.Errorf("player1 budget = %d, want 5000", gs.GetBudget(1))
	}
	if gs.GetBudget(2) != 4000 {
		t.Errorf("player2 budget = %d, want 4000", gs.GetBudget(2))
	}

	gs.SetBudget(1, 3000)
	gs.SetBudget(2, 6000)

	if gs.GetBudget(1) != 3000 {
		t.Errorf("player1 budget = %d, want 3000", gs.GetBudget(1))
	}
	if gs.GetBudget(2) != 6000 {
		t.Errorf("player2 budget = %d, want 6000", gs.GetBudget(2))
	}
}

// --- Insight Pool ---

func TestGetSetInsightPool(t *testing.T) {
	gs := newTestGameState()

	if gs.GetInsightPool(1) != 500 {
		t.Errorf("player1 insight = %d, want 500", gs.GetInsightPool(1))
	}
	if gs.GetInsightPool(2) != 300 {
		t.Errorf("player2 insight = %d, want 300", gs.GetInsightPool(2))
	}

	gs.SetInsightPool(1, 1000)
	if gs.GetInsightPool(1) != 1000 {
		t.Errorf("player1 insight = %d, want 1000", gs.GetInsightPool(1))
	}
}

// --- Field Round-Trip ---

func TestFieldRoundTrip(t *testing.T) {
	gs := newTestGameState()

	tp := int64(700)
	field := &Field{
		Frontend: [3]*ResourceInstance{
			{InstanceID: "f1", CardID: 1, CurrentTP: &tp, MaxAV: 1400},
		},
		Backend: [3]*ResourceInstance{
			{InstanceID: "b1", CardID: 3, MaxAV: 1300},
		},
	}

	if err := gs.SetField(1, field); err != nil {
		t.Fatalf("SetField: %v", err)
	}

	got, err := gs.GetField(1)
	if err != nil {
		t.Fatalf("GetField: %v", err)
	}

	if got.Frontend[0] == nil || got.Frontend[0].InstanceID != "f1" {
		t.Error("frontend[0] should be f1")
	}
	if got.Frontend[0].CurrentTP == nil || *got.Frontend[0].CurrentTP != 700 {
		t.Error("frontend[0] TP should be 700")
	}
	if got.Backend[0] == nil || got.Backend[0].InstanceID != "b1" {
		t.Error("backend[0] should be b1")
	}
	if got.Frontend[1] != nil {
		t.Error("frontend[1] should be nil")
	}
}

func TestFieldRoundTrip_Player2(t *testing.T) {
	gs := newTestGameState()

	field := &Field{
		Support: [3]*SupportInstance{
			{InstanceID: "s1", CardID: 10, FaceDown: true},
		},
	}

	if err := gs.SetField(2, field); err != nil {
		t.Fatalf("SetField: %v", err)
	}

	got, err := gs.GetField(2)
	if err != nil {
		t.Fatalf("GetField: %v", err)
	}

	if got.Support[0] == nil || !got.Support[0].FaceDown {
		t.Error("support[0] should be face-down")
	}
}

// --- Hand Round-Trip ---

func TestHandRoundTrip(t *testing.T) {
	gs := newTestGameState()

	hand := []HandCard{
		{InstanceID: "h1", CardID: 1},
		{InstanceID: "h2", CardID: 2},
		{InstanceID: "h3", CardID: 3},
	}

	if err := gs.SetHand(1, hand); err != nil {
		t.Fatalf("SetHand: %v", err)
	}

	got, err := gs.GetHand(1)
	if err != nil {
		t.Fatalf("GetHand: %v", err)
	}

	if len(got) != 3 {
		t.Fatalf("hand length = %d, want 3", len(got))
	}
	if got[0].CardID != 1 || got[1].CardID != 2 || got[2].CardID != 3 {
		t.Error("hand card IDs mismatch")
	}
}

// --- Repository Round-Trip ---

func TestRepositoryRoundTrip(t *testing.T) {
	gs := newTestGameState()

	repo := []int64{10, 20, 30, 40, 50}
	if err := gs.SetRepository(2, repo); err != nil {
		t.Fatalf("SetRepository: %v", err)
	}

	got, err := gs.GetRepository(2)
	if err != nil {
		t.Fatalf("GetRepository: %v", err)
	}

	if len(got) != 5 {
		t.Fatalf("repo length = %d, want 5", len(got))
	}
	if got[0] != 10 || got[4] != 50 {
		t.Error("repo contents mismatch")
	}
}

// --- Trash Round-Trip ---

func TestTrashRoundTrip(t *testing.T) {
	gs := newTestGameState()

	trash := []int64{99, 88}
	if err := gs.SetTrash(1, trash); err != nil {
		t.Fatalf("SetTrash: %v", err)
	}

	got, err := gs.GetTrash(1)
	if err != nil {
		t.Fatalf("GetTrash: %v", err)
	}

	if len(got) != 2 || got[0] != 99 {
		t.Errorf("trash = %v, want [99, 88]", got)
	}
}

// --- Time Bank ---

func TestGetSetTimeBank(t *testing.T) {
	gs := newTestGameState()

	if gs.GetTimeBank(1) != 480 {
		t.Errorf("player1 time bank = %d, want 480", gs.GetTimeBank(1))
	}
	if gs.GetTimeBank(2) != 360 {
		t.Errorf("player2 time bank = %d, want 360", gs.GetTimeBank(2))
	}

	gs.SetTimeBank(1, 100)
	if gs.GetTimeBank(1) != 100 {
		t.Errorf("player1 time bank = %d, want 100", gs.GetTimeBank(1))
	}
}

// --- Chain Stack Round-Trip ---

func TestChainStackRoundTrip(t *testing.T) {
	gs := newTestGameState()

	stack := []ChainEntry{
		{ChainLevel: 1, ActionType: "attack", SourcePlayerID: "p1", SourceInstanceID: "f1"},
		{ChainLevel: 2, ActionType: "reactive", SourcePlayerID: "p2", SourceInstanceID: "s1"},
	}

	if err := gs.SetChainStack(stack); err != nil {
		t.Fatalf("SetChainStack: %v", err)
	}

	got, err := gs.GetChainStack()
	if err != nil {
		t.Fatalf("GetChainStack: %v", err)
	}

	if len(got) != 2 {
		t.Fatalf("chain length = %d, want 2", len(got))
	}
	if got[0].ChainLevel != 1 || got[0].ActionType != "attack" {
		t.Error("chain entry 0 mismatch")
	}
	if got[1].ChainLevel != 2 || got[1].ActionType != "reactive" {
		t.Error("chain entry 1 mismatch")
	}
}

func TestChainStackEmpty(t *testing.T) {
	gs := newTestGameState()

	// Set empty chain
	if err := gs.SetChainStack(nil); err != nil {
		t.Fatalf("SetChainStack: %v", err)
	}

	got, err := gs.GetChainStack()
	if err != nil {
		t.Fatalf("GetChainStack: %v", err)
	}

	if len(got) != 0 {
		t.Errorf("chain length = %d, want 0", len(got))
	}
}

// --- Utility Functions ---

func TestOpponentNum(t *testing.T) {
	tests := []struct {
		playerNum int64
		want      int64
	}{
		{1, 2},
		{2, 1},
	}
	for _, tt := range tests {
		if got := OpponentNum(tt.playerNum); got != tt.want {
			t.Errorf("OpponentNum(%d) = %d, want %d", tt.playerNum, got, tt.want)
		}
	}
}

func TestPlayerNumForID(t *testing.T) {
	game := &Game{
		Player1ID: "alice",
		Player2ID: "bob",
	}

	if PlayerNumForID(game, "alice") != 1 {
		t.Error("alice should be player 1")
	}
	if PlayerNumForID(game, "bob") != 2 {
		t.Error("bob should be player 2")
	}
	if PlayerNumForID(game, "charlie") != 0 {
		t.Error("unknown player should return 0")
	}
}

func TestPlayerIDForNum(t *testing.T) {
	game := &Game{
		Player1ID: "alice",
		Player2ID: "bob",
	}

	if PlayerIDForNum(game, 1) != "alice" {
		t.Error("player 1 should be alice")
	}
	if PlayerIDForNum(game, 2) != "bob" {
		t.Error("player 2 should be bob")
	}
}
