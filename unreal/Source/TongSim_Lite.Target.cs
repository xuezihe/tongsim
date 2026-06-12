// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class TongSim_LiteTarget : TargetRules
{
	public TongSim_LiteTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V6;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_6;
		ExtraModuleNames.Add("TongSim_Lite");

        // grpc������dllʹ�õ���ANSI�ڴ��������UEĬ��ʹ�õ���FMalloc��������
        // ʹ���������ΪANSI�ڴ������������grpc�����UE�����ݽ���ʱ������ڴ���䲻ƥ��Ĵ���
        // ֻ��Windows����������⣬Linux��û���������
        GlobalDefinitions.Add("FORCE_ANSI_ALLOCATOR=1");
        GlobalDefinitions.Add("UE_USE_MALLOC_FILL_BYTES=0");
    }
}
