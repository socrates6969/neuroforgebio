// UNVERIFIED IN-EDITOR (never compiled by UBT/UHT). See README.md "Verification status".
#include "NeuroForgeBlueprintLibrary.h"

#include "NeuroForgeLog.h"
#include "NeuroForgeModule.h"

THIRD_PARTY_INCLUDES_START
#include "neuroforge.hpp"
THIRD_PARTY_INCLUDES_END

namespace
{
	// Run F; on a neuroforge::Error log it and report failure (exceptions never reach Blueprint VM).
	template <class F>
	FString Guard(F&& Fn, bool& bSuccess)
	{
		bSuccess = false;
		if (!FNeuroForgeModule::IsAvailable())
		{
			UE_LOG(LogNeuroForge, Warning, TEXT("NeuroForge core not available: %s"), *FNeuroForgeModule::GetLoadError());
			return FString();
		}
		try
		{
			const std::string R = Fn();
			bSuccess = true;
			return UTF8_TO_TCHAR(R.c_str());
		}
		catch (const std::exception& E)
		{
			UE_LOG(LogNeuroForge, Warning, TEXT("%s"), UTF8_TO_TCHAR(E.what()));
			return FString();
		}
	}
}

FString UNeuroForgeBlueprintLibrary::CoreVersion()
{
	return FNeuroForgeModule::IsAvailable() ? FString(UTF8_TO_TCHAR(nf_core_version())) : FString();
}

bool UNeuroForgeBlueprintLibrary::IsCoreAvailable()
{
	return FNeuroForgeModule::IsAvailable();
}

FString UNeuroForgeBlueprintLibrary::BlobIdOfBytes(const TArray<uint8>& Data, bool& bSuccess)
{
	return Guard([&] { return neuroforge::blob_id(Data.GetData(), static_cast<size_t>(Data.Num())); }, bSuccess);
}

FString UNeuroForgeBlueprintLibrary::BlobIdOfString(const FString& Text, bool& bSuccess)
{
	const FTCHARToUTF8 Utf8(*Text);
	return Guard([&] { return neuroforge::blob_id(Utf8.Get(), static_cast<size_t>(Utf8.Length())); }, bSuccess);
}

FString UNeuroForgeBlueprintLibrary::BlobIdOfFile(const FString& Path, int64& SizeBytes, bool& bSuccess)
{
	SizeBytes = 0;
	return Guard([&] {
		auto R = neuroforge::blob_id_file(TCHAR_TO_UTF8(*Path));
		SizeBytes = static_cast<int64>(R.second);
		return R.first;
	}, bSuccess);
}

FString UNeuroForgeBlueprintLibrary::CanonicalizeJson(const FString& Json, bool& bSuccess)
{
	const FTCHARToUTF8 Utf8(*Json);
	return Guard([&] { return neuroforge::canonicalize(std::string_view(Utf8.Get(), static_cast<size_t>(Utf8.Length()))); }, bSuccess);
}

bool UNeuroForgeBlueprintLibrary::IsValidId(const FString& Id)
{
	return FNeuroForgeModule::IsAvailable() && neuroforge::is_valid_id(TCHAR_TO_UTF8(*Id));
}
