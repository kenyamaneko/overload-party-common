package model

import (
	"encoding/json"
	"fmt"
)

// --- Budget ---

func (gs *GameState) GetBudget(playerNum int64) int64 {
	if playerNum == 1 {
		return gs.Player1Budget
	}
	return gs.Player2Budget
}

func (gs *GameState) SetBudget(playerNum, val int64) {
	if playerNum == 1 {
		gs.Player1Budget = val
	} else {
		gs.Player2Budget = val
	}
}

// --- Insight Pool ---

func (gs *GameState) GetInsightPool(playerNum int64) int64 {
	if playerNum == 1 {
		return gs.Player1InsightPool
	}
	return gs.Player2InsightPool
}

func (gs *GameState) SetInsightPool(playerNum, val int64) {
	if playerNum == 1 {
		gs.Player1InsightPool = val
	} else {
		gs.Player2InsightPool = val
	}
}

// --- Field ---

func (gs *GameState) GetField(playerNum int64) (*Field, error) {
	raw := gs.Player1Field
	if playerNum == 2 {
		raw = gs.Player2Field
	}
	var f Field
	if err := json.Unmarshal(raw, &f); err != nil {
		return nil, fmt.Errorf("unmarshal player%d field: %w", playerNum, err)
	}
	return &f, nil
}

func (gs *GameState) SetField(playerNum int64, f *Field) error {
	data, err := json.Marshal(f)
	if err != nil {
		return fmt.Errorf("marshal player%d field: %w", playerNum, err)
	}
	if playerNum == 1 {
		gs.Player1Field = data
	} else {
		gs.Player2Field = data
	}
	return nil
}

// --- Hand ---

func (gs *GameState) GetHand(playerNum int64) ([]HandCard, error) {
	raw := gs.Player1Hand
	if playerNum == 2 {
		raw = gs.Player2Hand
	}
	var hand []HandCard
	if err := json.Unmarshal(raw, &hand); err != nil {
		return nil, fmt.Errorf("unmarshal player%d hand: %w", playerNum, err)
	}
	return hand, nil
}

func (gs *GameState) SetHand(playerNum int64, hand []HandCard) error {
	data, err := json.Marshal(hand)
	if err != nil {
		return fmt.Errorf("marshal player%d hand: %w", playerNum, err)
	}
	if playerNum == 1 {
		gs.Player1Hand = data
	} else {
		gs.Player2Hand = data
	}
	return nil
}

// --- Repository ---

func (gs *GameState) GetRepository(playerNum int64) ([]int64, error) {
	raw := gs.Player1Repository
	if playerNum == 2 {
		raw = gs.Player2Repository
	}
	var repo []int64
	if err := json.Unmarshal(raw, &repo); err != nil {
		return nil, fmt.Errorf("unmarshal player%d repository: %w", playerNum, err)
	}
	return repo, nil
}

func (gs *GameState) SetRepository(playerNum int64, repo []int64) error {
	data, err := json.Marshal(repo)
	if err != nil {
		return fmt.Errorf("marshal player%d repository: %w", playerNum, err)
	}
	if playerNum == 1 {
		gs.Player1Repository = data
	} else {
		gs.Player2Repository = data
	}
	return nil
}

// --- Trash ---

func (gs *GameState) GetTrash(playerNum int64) ([]int64, error) {
	raw := gs.Player1Trash
	if playerNum == 2 {
		raw = gs.Player2Trash
	}
	var trash []int64
	if err := json.Unmarshal(raw, &trash); err != nil {
		return nil, fmt.Errorf("unmarshal player%d trash: %w", playerNum, err)
	}
	return trash, nil
}

func (gs *GameState) SetTrash(playerNum int64, trash []int64) error {
	data, err := json.Marshal(trash)
	if err != nil {
		return fmt.Errorf("marshal player%d trash: %w", playerNum, err)
	}
	if playerNum == 1 {
		gs.Player1Trash = data
	} else {
		gs.Player2Trash = data
	}
	return nil
}

// --- Time Bank ---

func (gs *GameState) GetTimeBank(playerNum int64) int64 {
	if playerNum == 1 {
		return gs.Player1TimeBank
	}
	return gs.Player2TimeBank
}

func (gs *GameState) SetTimeBank(playerNum, val int64) {
	if playerNum == 1 {
		gs.Player1TimeBank = val
	} else {
		gs.Player2TimeBank = val
	}
}

// --- Chain Stack ---

func (gs *GameState) GetChainStack() ([]ChainEntry, error) {
	if len(gs.ChainStack) == 0 || string(gs.ChainStack) == "null" {
		return nil, nil
	}
	var stack []ChainEntry
	if err := json.Unmarshal(gs.ChainStack, &stack); err != nil {
		return nil, fmt.Errorf("unmarshal chain stack: %w", err)
	}
	return stack, nil
}

func (gs *GameState) SetChainStack(stack []ChainEntry) error {
	if len(stack) == 0 {
		gs.ChainStack = nil
		return nil
	}
	data, err := json.Marshal(stack)
	if err != nil {
		return fmt.Errorf("marshal chain stack: %w", err)
	}
	gs.ChainStack = data
	return nil
}

// --- Utility ---

// PlayerNumForID returns 1 or 2 given a player ID, using the parent Game.
// Returns 0 if the player is not in the game.
func PlayerNumForID(game *Game, playerID string) int64 {
	if game.Player1ID == playerID {
		return 1
	}
	if game.Player2ID == playerID {
		return 2
	}
	return 0
}

// OpponentNum returns the opposite player number.
func OpponentNum(playerNum int64) int64 {
	if playerNum == 1 {
		return 2
	}
	return 1
}

// PlayerIDForNum returns the player ID for a given player number.
func PlayerIDForNum(game *Game, playerNum int64) string {
	if playerNum == 1 {
		return game.Player1ID
	}
	return game.Player2ID
}

// HasTemporaryEffect returns true if the resource has an active effect of the given type.
func HasTemporaryEffect(res *ResourceInstance, effectType string) bool {
	for _, e := range res.TemporaryEffects {
		if e.EffectType == effectType {
			return true
		}
	}
	return false
}

// CountDeployedThisTurn counts frontend and backend resources deployed on the given turn.
func CountDeployedThisTurn(field *Field, turn int64) int {
	count := 0
	for _, r := range field.Frontend {
		if r != nil && r.DeployedOnTurn == turn {
			count++
		}
	}
	for _, r := range field.Backend {
		if r != nil && r.DeployedOnTurn == turn {
			count++
		}
	}
	return count
}

// NextDeployOrder scans both players' fields and returns the next available deploy order.
func (gs *GameState) NextDeployOrder() int64 {
	maxOrder := int64(0)
	for _, pNum := range []int64{1, 2} {
		field, err := gs.GetField(pNum)
		if err != nil {
			continue
		}
		for _, res := range field.Frontend {
			if res != nil && res.DeployOrder > maxOrder {
				maxOrder = res.DeployOrder
			}
		}
		for _, res := range field.Backend {
			if res != nil && res.DeployOrder > maxOrder {
				maxOrder = res.DeployOrder
			}
		}
		for _, sup := range field.Support {
			if sup != nil && sup.DeployOrder > maxOrder {
				maxOrder = sup.DeployOrder
			}
		}
	}
	return maxOrder + 1
}
