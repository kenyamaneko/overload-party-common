package model

import "time"

// UserSettings holds per-player application settings.
type UserSettings struct {
	PlayerID    string    `json:"player_id"`
	Language    string    `json:"language"`
	BgmVolume   int64     `json:"bgm_volume"`
	SeVolume    int64     `json:"se_volume"`
	PushEnabled bool      `json:"push_enabled"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// DefaultUserSettings returns initial settings for a newly registered player.
func DefaultUserSettings(playerID string) *UserSettings {
	return &UserSettings{
		PlayerID:    playerID,
		Language:    "ja",
		BgmVolume:   50,
		SeVolume:    50,
		PushEnabled: true,
		UpdatedAt:   time.Now(),
	}
}
