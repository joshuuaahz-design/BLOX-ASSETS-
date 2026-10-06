--!strict
-- Shadow Puffer avatar: every setting in one place.
-- Put this ModuleScript in ReplicatedStorage, named "AvatarConfig".
-- After uploading the PNGs in ../out (Create > Shirts / Pants / Decals), paste their asset IDs below.
-- Catalog IDs for hair and glasses come from the item's URL: roblox.com/catalog/<ID>/...

local AvatarConfig = {}

AvatarConfig.Name = "ShadowPuffer"

-- Skin: the light tan from the reference picture.
AvatarConfig.SkinColor = Color3.fromRGB(204, 178, 149)

-- Classic clothing (from out/shirt_template.png, out/pants_template.png). 0 = none.
AvatarConfig.ShirtId = 0
AvatarConfig.PantsId = 0

-- Face (from out/face_decal.png, uploaded as a Decal). 0 = keep the default face.
AvatarConfig.FaceId = 0

-- Accessories. Pick from the catalog: a messy black hair and round black glasses
-- (if your glasses are already on the face decal, leave GlassesIds empty).
AvatarConfig.HairIds = { 0 } -- e.g. { 1234567890 }
AvatarConfig.GlassesIds = {} -- face accessories
AvatarConfig.NeckIds = {} -- optional: a hood or scarf accessory to bulk up the collar

-- Body: slightly narrow and tall, like the reference.
AvatarConfig.Scale = {
	Height = 1.0,
	Width = 0.9,
	Depth = 0.95,
	Head = 1.0,
	BodyType = 0.0,
	Proportion = 0.0,
}

-- Body parts (bundle part IDs). 0 = default blocky R15 parts.
AvatarConfig.BodyParts = {
	Head = 0,
	Torso = 0,
	LeftArm = 0,
	RightArm = 0,
	LeftLeg = 0,
	RightLeg = 0,
}

-- Animations (catalog animation IDs). 0 = Roblox default.
AvatarConfig.Animations = {
	Idle = 0,
	Walk = 0,
	Run = 0,
	Jump = 0,
	Fall = 0,
}

-- true: every player who joins wears this avatar. false: only the display rig is built.
AvatarConfig.ApplyToPlayers = false

-- Where the display rig stands.
AvatarConfig.RigPosition = Vector3.new(0, 5, 0)

return AvatarConfig
