// Code generated support file; DO NOT EDIT.
namespace OverloadParty.GameData;

using System.Reflection;

public static class EmbeddedCards
{
    public static Stream GetCardsJsonStream()
        => Assembly.GetExecutingAssembly()
            .GetManifestResourceStream("OverloadParty.GameData.cache.cards_gen.json")
            ?? throw new InvalidOperationException("Embedded cards_gen.json not found");
}
