// UNVERIFIED IN-EDITOR (never compiled by UBT/UHT). See README.md "Verification status".
#include "NeuroForgeStreamComponent.h"

#include "Misc/Paths.h"
#include "NeuroForgeLog.h"
#include "NeuroForgeModule.h"

THIRD_PARTY_INCLUDES_START
#include "NeuroForgeCore/NfReplay.h"
#include "NeuroForgeCore/NfStreamState.h"
THIRD_PARTY_INCLUDES_END

UNeuroForgeStreamComponent::UNeuroForgeStreamComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
}

// Out of line so std::unique_ptr sees the complete worker types.
UNeuroForgeStreamComponent::~UNeuroForgeStreamComponent() = default;

bool UNeuroForgeStreamComponent::StartStream()
{
	StopStream();
	if (!FNeuroForgeModule::IsAvailable())
	{
		Fail(FNeuroForgeModule::GetLoadError());
		return false;
	}
	const FString Root = FPaths::IsRelative(RecordingRoot) ? FPaths::Combine(FPaths::ProjectContentDir(), RecordingRoot) : RecordingRoot;
	try
	{
		neuroforge::Recording Rec(TCHAR_TO_UTF8(*FPaths::ConvertRelativePathToFull(Root)), TCHAR_TO_UTF8(*RecordingId));
		nf::engine::ReplayOptions Opt;
		Opt.speed = FMath::Max(0.01, static_cast<double>(PlaybackSpeed));
		Opt.loop = bLoop;
		Opt.block_samples = static_cast<uint32_t>(FMath::Max(1, BlockSamples));
		Worker = std::make_unique<nf::engine::ReplayWorker>(std::move(Rec), Opt);
		State = std::make_unique<nf::engine::StreamState>();
		State->reset(Worker->channel_names(), Worker->sample_rate());
		LatestCache.Init(0.f, static_cast<int32>(Worker->n_channels()));
		bCompletedRaised = false;
		Worker->start();
	}
	catch (const std::exception& E)
	{
		Worker.reset();
		State.reset();
		Fail(UTF8_TO_TCHAR(E.what()));
		return false;
	}
	SetComponentTickEnabled(true);
	return true;
}

void UNeuroForgeStreamComponent::StopStream()
{
	Generation++;
	if (Worker)
	{
		Worker->stop(); // joins the worker thread
		Worker.reset();
	}
	SetComponentTickEnabled(false);
}

bool UNeuroForgeStreamComponent::IsStreaming() const
{
	return Worker && !Worker->error() && !(Worker->completed() && Worker->queued() == 0);
}

TArray<float> UNeuroForgeStreamComponent::GetLatestValues() const
{
	return LatestCache;
}

float UNeuroForgeStreamComponent::GetChannelValue(const FString& Channel) const
{
	return State ? State->value(TCHAR_TO_UTF8(*Channel)) : NAN;
}

TArray<FString> UNeuroForgeStreamComponent::GetChannelNames() const
{
	TArray<FString> Out;
	if (State)
	{
		for (const std::string& N : State->names())
		{
			Out.Add(UTF8_TO_TCHAR(N.c_str()));
		}
	}
	return Out;
}

float UNeuroForgeStreamComponent::GetSampleRate() const
{
	return State ? static_cast<float>(State->sample_rate()) : 0.f;
}

int64 UNeuroForgeStreamComponent::GetCurrentSample() const
{
	return State ? State->current_sample() : -1;
}

int64 UNeuroForgeStreamComponent::GetDroppedBlocks() const
{
	return Worker ? static_cast<int64>(Worker->dropped_blocks()) : 0;
}

void UNeuroForgeStreamComponent::BeginPlay()
{
	Super::BeginPlay();
	if (bAutoStart && !RecordingId.IsEmpty())
	{
		StartStream();
	}
}

void UNeuroForgeStreamComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	StopStream();
	Super::EndPlay(EndPlayReason);
}

void UNeuroForgeStreamComponent::BeginDestroy()
{
	// Join the worker without touching tick registration (the component may be half torn down).
	if (Worker)
	{
		Worker->stop();
		Worker.reset();
	}
	Super::BeginDestroy();
}

void UNeuroForgeStreamComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (!Worker)
	{
		return;
	}
	nf::engine::SampleBlock Block;
	for (int32 I = 0; I < MaxBlocksPerTick && Worker->try_pop(Block); I++)
	{
		State->apply(Block);
		const std::vector<float>& L = State->latest();
		for (int32 C = 0; C < LatestCache.Num() && C < static_cast<int32>(L.size()); C++)
		{
			LatestCache[C] = L[C];
		}
		const uint32 Gen = Generation;
		OnSamples.Broadcast(LatestCache, static_cast<int64>(Block.first_sample), static_cast<int32>(Block.rows));
		if (Gen != Generation || !Worker)
		{
			return; // a handler called StopStream or StartStream: this tick's loop belongs to the old stream
		}
	}
	const std::optional<std::string> Err = Worker->error();
	if (Err)
	{
		StopStream();
		Fail(UTF8_TO_TCHAR(Err->c_str()));
	}
	else if (Worker->completed() && Worker->queued() == 0 && !bCompletedRaised)
	{
		bCompletedRaised = true;
		OnCompleted.Broadcast();
	}
}

void UNeuroForgeStreamComponent::Fail(const FString& Message)
{
	UE_LOG(LogNeuroForge, Error, TEXT("%s: %s"), *GetNameSafe(GetOwner()), *Message);
	OnError.Broadcast(Message);
}
