-- Shadow Puffer avatar builder.
-- Put this Script in ServerScriptService. It reads ReplicatedStorage.AvatarConfig,
-- builds an R15 rig named after the config into Workspace and, if ApplyToPlayers is
-- true, dresses every player in the same look.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("AvatarConfig"))

local function idList(ids: { number }): string
	local kept = {}
	for _, id in ids do
		if id and id > 0 then
			table.insert(kept, tostring(id))
		end
	end
	return table.concat(kept, ",")
end

local function makeDescription(): HumanoidDescription
	local d = Instance.new("HumanoidDescription")

	for _, part in { "HeadColor", "TorsoColor", "LeftArmColor", "RightArmColor", "LeftLegColor", "RightLegColor" } do
		(d :: any)[part] = Config.SkinColor
	end

	d.Shirt = Config.ShirtId
	d.Pants = Config.PantsId
	d.Face = Config.FaceId

	d.HairAccessory = idList(Config.HairIds)
	d.FaceAccessory = idList(Config.GlassesIds)
	d.NeckAccessory = idList(Config.NeckIds)

	d.HeightScale = Config.Scale.Height
	d.WidthScale = Config.Scale.Width
	d.DepthScale = Config.Scale.Depth
	d.HeadScale = Config.Scale.Head
	d.BodyTypeScale = Config.Scale.BodyType
	d.ProportionScale = Config.Scale.Proportion

	d.Head = Config.BodyParts.Head
	d.Torso = Config.BodyParts.Torso
	d.LeftArm = Config.BodyParts.LeftArm
	d.RightArm = Config.BodyParts.RightArm
	d.LeftLeg = Config.BodyParts.LeftLeg
	d.RightLeg = Config.BodyParts.RightLeg

	d.IdleAnimation = Config.Animations.Idle
	d.WalkAnimation = Config.Animations.Walk
	d.RunAnimation = Config.Animations.Run
	d.JumpAnimation = Config.Animations.Jump
	d.FallAnimation = Config.Animations.Fall

	return d
end

-- Display rig in the world
local ok, rig = pcall(function()
	return Players:CreateHumanoidModelFromDescription(makeDescription(), Enum.HumanoidRigType.R15)
end)
if ok and rig then
	rig.Name = Config.Name
	rig:PivotTo(CFrame.new(Config.RigPosition))
	local root = rig:FindFirstChild("HumanoidRootPart") :: BasePart?
	if root then
		root.Anchored = true
	end
	rig.Parent = workspace
else
	warn("[AvatarBuilder] could not build rig:", rig)
end

-- Optional: dress every player
if Config.ApplyToPlayers then
	local function dress(player: Player)
		player.CharacterAppearanceLoaded:Connect(function(character)
			local humanoid = character:FindFirstChildOfClass("Humanoid")
			if humanoid then
				local applied, err = pcall(function()
					humanoid:ApplyDescription(makeDescription())
				end)
				if not applied then
					warn("[AvatarBuilder] ApplyDescription failed for", player.Name, err)
				end
			end
		end)
	end
	Players.PlayerAdded:Connect(dress)
	for _, p in Players:GetPlayers() do
		dress(p)
	end
end
