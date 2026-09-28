// UNVERIFIED IN-EDITOR (never compiled by UBT/UHT). The logic it wraps (NeuroForgeCore/NfReplay.h,
// NfStreamState.h) is compiled and tested with MSVC; this shell is not. See README.md.
#pragma once

#include "Components/ActorComponent.h"
#include "CoreMinimal.h"

#include <memory>

#include "NeuroForgeStreamComponent.generated.h"

namespace nf { namespace engine { class ReplayWorker; class StreamState; } }

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FNeuroForgeSamplesEvent, const TArray<float>&, LatestValues, int64, FirstSample, int32, Rows);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FNeuroForgeErrorEvent, const FString&, Message);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FNeuroForgeCompletedEvent);

/**
 * Replays a NeuroForge recording (nf-signal/1) in scaled real time and exposes the samples to
 * Blueprints and gameplay code. Samples are read on a worker thread and delivered on the game
 * thread in TickComponent, so every event handler runs on the game thread.
 * Reads data only: there is no way to send anything to a device from here.
 */
UCLASS(ClassGroup = (NeuroForge), meta = (BlueprintSpawnableComponent, DisplayName = "NeuroForge Stream"))
class NEUROFORGE_API UNeuroForgeStreamComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNeuroForgeStreamComponent();
	virtual ~UNeuroForgeStreamComponent() override;

	/** Zarr root directory. A relative path is resolved against the project's Content directory. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NeuroForge")
	FString RecordingRoot = TEXT("NeuroForge");

	/** Recording ID under the root, for example rec-001. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NeuroForge")
	FString RecordingId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NeuroForge")
	bool bLoop = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NeuroForge", meta = (ClampMin = "0.01"))
	float PlaybackSpeed = 1.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NeuroForge")
	bool bAutoStart = true;

	/** Samples per block delivered to OnSamples. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NeuroForge", meta = (ClampMin = "1"))
	int32 BlockSamples = 32;

	/** Most blocks delivered per tick; the rest wait for the next tick. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "NeuroForge", meta = (ClampMin = "1"))
	int32 MaxBlocksPerTick = 64;

	/** Raised on the game thread for every block: the newest value per channel, and the block's range. */
	UPROPERTY(BlueprintAssignable, Category = "NeuroForge")
	FNeuroForgeSamplesEvent OnSamples;

	UPROPERTY(BlueprintAssignable, Category = "NeuroForge")
	FNeuroForgeErrorEvent OnError;

	/** Raised once when a non-looping replay has delivered its last block. */
	UPROPERTY(BlueprintAssignable, Category = "NeuroForge")
	FNeuroForgeCompletedEvent OnCompleted;

	/** Open the recording and start replaying. Returns false (and raises OnError) on failure. */
	UFUNCTION(BlueprintCallable, Category = "NeuroForge")
	bool StartStream();

	UFUNCTION(BlueprintCallable, Category = "NeuroForge")
	void StopStream();

	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	bool IsStreaming() const;

	/** Newest physical value per channel (stored * scale + offset), in the channel units. */
	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	TArray<float> GetLatestValues() const;

	/** Newest value of one channel; NaN if unknown or before the first block. */
	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	float GetChannelValue(const FString& Channel) const;

	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	TArray<FString> GetChannelNames() const;

	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	float GetSampleRate() const;

	/** Recording index of the newest delivered sample (-1 before the first block). */
	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	int64 GetCurrentSample() const;

	UFUNCTION(BlueprintPure, Category = "NeuroForge")
	int64 GetDroppedBlocks() const;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void BeginDestroy() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	void Fail(const FString& Message);

	std::unique_ptr<nf::engine::ReplayWorker> Worker;
	std::unique_ptr<nf::engine::StreamState> State;
	TArray<float> LatestCache;
	bool bCompletedRaised = false;
	uint32 Generation = 0; // bumped by Start/StopStream so TickComponent notices re-entrant calls from handlers
};
