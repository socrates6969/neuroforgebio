// UNVERIFIED IN-EDITOR (never compiled by UBT). See README.md "Verification status".
#pragma once

#include "Modules/ModuleManager.h"

class NEUROFORGE_API FNeuroForgeModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

	/** Whether neuroforge.dll was loaded and its ABI is compatible with the bundled header. */
	static bool IsAvailable();

	/** Why the library is unavailable (empty when it is available). */
	static const FString& GetLoadError();

private:
	void* DllHandle = nullptr;
};
