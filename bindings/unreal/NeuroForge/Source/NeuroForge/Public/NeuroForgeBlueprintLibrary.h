// UNVERIFIED IN-EDITOR (never compiled by UBT/UHT). See README.md "Verification status".
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"

#include "NeuroForgeBlueprintLibrary.generated.h"

/** Content IDs and verification helpers from the NeuroForge core, for Blueprints. */
UCLASS()
class NEUROFORGE_API UNeuroForgeBlueprintLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Version of nf-core inside neuroforge.dll (empty if the library is not loaded). */
	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	static FString CoreVersion();

	/** Whether neuroforge.dll is loaded and ABI-compatible. */
	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	static bool IsCoreAvailable();

	/** blob:sha256:<hex> of raw bytes. Empty and bSuccess = false on failure. */
	UFUNCTION(BlueprintCallable, Category = "NeuroForge")
	static FString BlobIdOfBytes(const TArray<uint8>& Data, bool& bSuccess);

	/** blob:sha256:<hex> of the UTF-8 encoding of a string. */
	UFUNCTION(BlueprintCallable, Category = "NeuroForge")
	static FString BlobIdOfString(const FString& Text, bool& bSuccess);

	/** Streaming blob ID of a file on disk. */
	UFUNCTION(BlueprintCallable, Category = "NeuroForge")
	static FString BlobIdOfFile(const FString& Path, int64& SizeBytes, bool& bSuccess);

	/** NF-CJSON v1 canonical form of a JSON document. */
	UFUNCTION(BlueprintCallable, Category = "NeuroForge")
	static FString CanonicalizeJson(const FString& Json, bool& bSuccess);

	/** Whether Id is a well-formed v1 content ID (blob|pv|chunk|provb:sha256:<64 hex>). */
	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	static bool IsValidId(const FString& Id);
};
