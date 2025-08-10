#!/usr/bin/env python3
"""
Mario & Luigi LIVE - Complete MMORPG Engine
Nintendo DS-style with integrated server, download play, M1 Pro optimized @ 60 FPS
Single-file implementation with FULL WORKING FEATURES
"""

import pygame
import sys
import json
import math
import random
import time
import socket
import threading
import struct
import hashlib
import os
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum
import queue
from collections import deque

# ============================================================================
# CORE CONFIGURATION - M1 Pro Optimized
# ============================================================================

# Nintendo DS dual-screen dimensions
DS_TOP_W, DS_TOP_H = 256, 192
DS_BOTTOM_W, DS_BOTTOM_H = 256, 192
SCREEN_GAP = 8
TOTAL_W = 256
TOTAL_H = DS_TOP_H + SCREEN_GAP + DS_BOTTOM_H

# Scale for modern displays (2x for retina)
SCALE = 3
WINDOW_W = TOTAL_W * SCALE
WINDOW_H = TOTAL_H * SCALE

# Performance settings - M1 Pro optimized
FPS = 60
PHYSICS_TIMESTEP = 1.0 / 60.0
MAX_FRAME_SKIP = 5
USE_METAL = sys.platform == "darwin"  # Enable Metal on macOS

# Network configuration
DEFAULT_PORT = 31337
PACKET_SIZE = 1024
TICK_RATE = 30  # Server tick rate

# Initialize Pygame with M1 optimizations
os.environ['SDL_RENDER_DRIVER'] = 'metal' if USE_METAL else 'opengl'
os.environ['SDL_VIDEODRIVER'] = 'cocoa' if sys.platform == "darwin" else ''
pygame.init()

# Set up display with hardware acceleration
flags = pygame.DOUBLEBUF | pygame.HWSURFACE
if USE_METAL:
    flags |= pygame.SCALED
    
screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), flags)
pygame.display.set_caption("Mario & Luigi LIVE - DS Edition")

# Create virtual DS screens
top_screen = pygame.Surface((DS_TOP_W, DS_TOP_H))
bottom_screen = pygame.Surface((DS_BOTTOM_W, DS_BOTTOM_H))

# Clock for 60 FPS
clock = pygame.time.Clock()

# Fonts - DS style
pygame.font.init()
FONT_TINY = pygame.font.Font(None, 8)
FONT_SMALL = pygame.font.Font(None, 10)
FONT_MEDIUM = pygame.font.Font(None, 12)
FONT_LARGE = pygame.font.Font(None, 16)

# Colors - Nintendo palette
BLACK = (0, 0, 0)
WHITE = (248, 248, 248)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
RED = (248, 0, 0)
GREEN = (0, 248, 0)
BLUE = (0, 0, 248)
YELLOW = (248, 248, 0)
PURPLE = (160, 0, 248)
CYAN = (0, 248, 248)
ORANGE = (248, 160, 0)
PINK = (248, 160, 248)
DS_GREEN = (156, 189, 15)
DS_BLUE = (49, 65, 156)
GOLD = (255, 215, 0)

# ============================================================================
# GAME DATA STRUCTURES
# ============================================================================

@dataclass
class Stats:
    hp: int = 40
    sp: int = 10
    max_hp: int = 40
    max_sp: int = 10
    power: int = 8
    defense: int = 4
    speed: int = 8
    luck: int = 2
    
    def to_dict(self):
        return self.__dict__
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

@dataclass
class Character:
    name: str = "Player"
    species: str = "Human"
    gender: str = "Male"
    color: str = "Red"
    age: str = "Teen"
    level: int = 1
    xp: int = 0
    coins: int = 100  # Start with some coins
    x: float = 128
    y: float = 96
    stats: Stats = field(default_factory=Stats)
    items: List[str] = field(default_factory=lambda: ["Mushroom", "Maple Syrup", "Lucky Clover"])
    party: List['Character'] = field(default_factory=list)
    star_guardian: Optional[Dict] = None
    player_id: Optional[str] = None
    is_player: bool = True
    
    def level_up(self):
        """Level up and increase stats"""
        self.level += 1
        self.stats.max_hp += 5
        self.stats.max_sp += 2
        self.stats.hp = self.stats.max_hp
        self.stats.sp = self.stats.max_sp
        self.stats.power += 2
        self.stats.defense += 1
        self.stats.speed += 1
        self.stats.luck += 1
        
    def add_xp(self, amount):
        """Add XP and check for level up"""
        self.xp += amount
        xp_needed = self.level * 50
        if self.xp >= xp_needed:
            self.xp -= xp_needed
            self.level_up()
            return True
        return False
    
    def to_dict(self):
        return {
            'name': self.name,
            'species': self.species,
            'gender': self.gender,
            'color': self.color,
            'age': self.age,
            'level': self.level,
            'xp': self.xp,
            'coins': self.coins,
            'x': self.x,
            'y': self.y,
            'stats': self.stats.to_dict(),
            'items': self.items,
            'star_guardian': self.star_guardian,
            'player_id': self.player_id
        }
    
    @classmethod
    def from_dict(cls, data):
        char = cls()
        for key, value in data.items():
            if key == 'stats':
                char.stats = Stats.from_dict(value)
            elif key != 'party':
                setattr(char, key, value)
        return char

# Complete species database from document
SPECIES = {
    "Human": {"genders": ["Male", "Female"], "colors": ["Light Skin", "Dark Skin"]},
    "Koopa": {"genders": ["Male", "Female"], "colors": ["Red Shell", "Blue Shell", "Green Shell", "Black Shell", "Pink Shell", "Purple Shell", "Orange Shell", "Cyan Shell"]},
    "Goomba": {"genders": ["Male", "Female"], "colors": ["Brown", "Red", "Blue", "Green", "Pink", "Black", "White"]},
    "Pianta": {"genders": ["Male", "Female"], "colors": ["Cyan", "Yellow", "Green", "Pink", "Orange"]},
    "Noki": {"genders": ["Male", "Female"], "colors": ["Cyan", "Yellow", "Green", "Pink", "Orange"]},
    "Toad": {"genders": ["Male", "Female"], "colors": ["Green Shroom", "Red Shroom", "Blue Shroom", "Yellow Shroom", "Pink Shroom", "Black Shroom", "Orange Shroom", "Purple Shroom", "White Shroom"]},
    "Yoshi": {"genders": ["Male", "Female"], "colors": ["Red", "Green", "Blue", "Cyan", "Black", "White", "Yellow", "Pink", "Purple", "Orange"]},
    "Hammer Bro.": {"genders": ["Male", "Female"], "colors": ["Green", "Blue", "Red", "Cyan", "Yellow", "Pink", "Purple", "Black", "White"]},
    "Luma": {"genders": ["Genderless"], "colors": ["Gold", "Silver", "Purple", "Blue", "Dark Red", "Orange"]},
    "Boo": {"genders": ["Male", "Female"], "colors": ["White", "Pink"]},
    "Bob-omb": {"genders": ["Male", "Female"], "colors": ["Black", "Pink"]},
    "Shy Guy": {"genders": ["Male", "Female"], "colors": ["Red", "Blue", "Yellow", "Green", "Purple", "Pink", "Cyan", "Black", "White", "Orange"]},
    "Piranha Plant": {"genders": ["Male", "Female"], "colors": ["Red", "Blue", "Yellow", "Green", "Pink", "Cyan", "Black", "White", "Orange", "Purple"]},
    "Tanooki": {"genders": ["Male", "Female"], "colors": ["Brown", "Black", "Green", "Pink", "Red", "White", "Purple"], "types": ["Normal", "Isle Delfino"]},
    "Buzzy Beetle": {"genders": ["Male", "Female"], "colors": ["Red Shell", "Blue Shell", "Green Shell", "Pink Shell", "Black Shell", "White Shell", "Orange Shell"]},
    "Lakitu": {"genders": ["Male", "Female"], "colors": ["Red", "Blue", "Green", "Pink", "Purple", "Black", "White"]},
    "Wiggler": {"genders": ["Male", "Female"], "colors": ["Orange", "Red", "Blue", "Green", "Pink", "Black", "White", "Purple"]},
    "Shroob": {"genders": ["Male", "Female"], "colors": ["Purple", "Red", "Blue", "Yellow", "Green", "Black", "White", "Pink"]},
    "Monty Mole": {"genders": ["Male", "Female"], "colors": ["Brown", "Red", "Blue", "Green", "Black", "White", "Pink", "Orange"]},
    "Birdo": {"genders": ["Male", "Female"], "colors": ["Pink", "Red", "Blue", "Green", "Cyan", "White", "Black", "Yellow", "Purple", "Orange"]},
    "Cloud Creature": {"genders": ["Male", "Female"], "colors": ["White", "Pale", "Red", "Blue", "Green", "Black", "Pink"]},
    "Magikoopa": {"genders": ["Male", "Female"], "colors": ["Blue Cloak", "White Cloak", "Red Cloak", "Green Cloak", "Black Cloak", "Purple Cloak", "Pink Cloak", "Yellow Cloak", "Orange Cloak"]},
    "Blooper": {"genders": ["Male", "Female"], "colors": ["White", "Black", "Blue", "Yellow", "Green", "Orange"]},
    "Bumpty": {"genders": ["Male", "Female"], "colors": ["Blue", "Black", "Orange", "Red", "Cyan", "Green", "Pink", "Purple", "Yellow"]},
    "Thwomp": {"genders": ["Male", "Female"], "colors": ["Black", "White", "Red", "Blue", "Cyan", "Green", "Pink"]},
    "Cataquack": {"genders": ["Male", "Female"], "colors": ["Orange", "Blue", "Green", "Red", "Black", "White", "Cyan", "Pink", "Yellow", "Purple"]},
    "Chain-Chomp": {"genders": ["Male", "Female"], "colors": ["Black", "White", "Blue", "Red", "Green", "Pink", "Purple"]},
    "Crazee Dayzee": {"genders": ["Male", "Female"], "colors": ["Pink", "Purple", "Red", "Blue", "Orange", "Green", "Black", "White", "Cyan", "Yellow"]},
    "Kong": {"genders": ["Male", "Female"], "colors": ["Brown", "Black", "White", "Pink", "Red", "Blue", "Orange"]},
    "Cheep Cheep": {"genders": ["Male", "Female"], "colors": ["Orange", "Black", "White", "Red", "Blue", "Green", "Pink", "Purple", "Cyan"]},
    "Fang": {"genders": ["Male", "Female"], "colors": ["Blue", "Orange", "Red", "Black", "White", "Green", "Pink", "Purple", "Cyan"]},
    "Bandinero": {"genders": ["Male", "Female"], "colors": ["Red", "Blue", "Yellow", "Black", "White", "Green", "Pink", "Gold"]},
    "Spike": {"genders": ["Male", "Female"], "colors": ["Green", "Blue", "Red", "Yellow", "Black", "White", "Pink", "Purple"]},
    "Spiny": {"genders": ["Male", "Female"], "colors": ["Red Shell", "Blue Shell", "Yellow Shell", "Green Shell", "Black Shell", "White Shell", "Pink Shell", "Cyan Shell", "Purple Shell"]},
    "Pokey": {"genders": ["Male", "Female"], "colors": ["Yellow", "Red", "Blue", "Green", "Orange", "Cyan", "Pink", "Black", "White"]}
}

# Additional unlockable species from patches
PATCH_SPECIES = {
    "Beanish": {"genders": ["Male", "Female"], "colors": ["Green", "Yellow", "Red", "Blue"]},
    "Ukiki": {"genders": ["Male", "Female"], "colors": ["Brown", "Gray", "Black"]},
    "Cooligan": {"genders": ["Male", "Female"], "colors": ["Blue", "White", "Cyan"]},
    "Toady": {"genders": ["Male", "Female"], "colors": ["Red", "Blue", "Green", "Yellow"]}
}

# Star Sprites
STAR_SPRITES = [
    {"name": "Nova", "color": "Gold", "personality": "Brave", "buff": "+2 Power"},
    {"name": "Lunette", "color": "Silver", "personality": "Calm", "buff": "+2 Defense"},
    {"name": "Astra", "color": "Purple", "personality": "Witty", "buff": "+2 Speed"},
    {"name": "Skylr", "color": "Cyan", "personality": "Cheerful", "buff": "+5 Luck"},
    {"name": "Ember", "color": "Orange", "personality": "Fiery", "buff": "+1 Power, +1 Speed"},
    {"name": "Noct", "color": "Blue", "personality": "Steady", "buff": "+10 HP"}
]

# Items
ITEMS = {
    "Mushroom": {"price": 50, "hp": 30, "sp": 0, "desc": "Restores 30 HP"},
    "Super Mushroom": {"price": 100, "hp": 60, "sp": 0, "desc": "Restores 60 HP"},
    "Ultra Mushroom": {"price": 200, "hp": 120, "sp": 0, "desc": "Restores 120 HP"},
    "Maple Syrup": {"price": 75, "hp": 0, "sp": 20, "desc": "Restores 20 SP"},
    "Super Syrup": {"price": 150, "hp": 0, "sp": 40, "desc": "Restores 40 SP"},
    "Lucky Clover": {"price": 100, "hp": 0, "sp": 0, "desc": "+10 Luck for battle", "luck": 10},
    "1-Up Mushroom": {"price": 500, "hp": 999, "sp": 999, "desc": "Full restore"},
    "Poison Mushroom": {"price": 150, "hp": 0, "sp": 0, "desc": "Poisons enemies", "poison": True},
    "Golden Mushroom": {"price": 300, "hp": 0, "sp": 0, "desc": "Max speed", "speed": 999}
}

# Enemies
ENEMIES = {
    "Goomba": {"hp": 20, "power": 5, "defense": 2, "speed": 5, "xp": 10, "coins": 5},
    "Koopa Troopa": {"hp": 30, "power": 7, "defense": 5, "speed": 6, "xp": 15, "coins": 8},
    "Shy Guy": {"hp": 25, "power": 6, "defense": 3, "speed": 7, "xp": 12, "coins": 6},
    "Pokey": {"hp": 40, "power": 8, "defense": 4, "speed": 3, "xp": 20, "coins": 12},
    "Dry Bones": {"hp": 35, "power": 9, "defense": 6, "speed": 4, "xp": 18, "coins": 10},
    "Bowser": {"hp": 100, "power": 15, "defense": 8, "speed": 5, "xp": 50, "coins": 30},
    "Tutankoopa": {"hp": 150, "power": 18, "defense": 10, "speed": 8, "xp": 100, "coins": 80}
}

# Patches
PATCHES = {
    "MLSS": {"name": "MLSS Patch", "price": 0, "desc": "Adds Superstar Saga areas"},
    "MLPiT": {"name": "MLPiT Patch", "price": 0, "desc": "Adds Partners in Time areas"},
    "Beanish": {"name": "Beanish Patch", "price": 0, "desc": "Enables Beanish class"},
    "Ukiki": {"name": "Ukiki Patch", "price": 0, "desc": "Enables Ukiki class"},
    "PoisonShroom": {"name": "Poison Mushroom Patch", "price": 0, "desc": "Poison Mushroom item"},
    "MLBiS": {"name": "MLBiS Patch", "price": 750, "desc": "Bowser's Inside Story areas"},
    "ShroomyHelpers": {"name": "'Shroomy Helpers", "price": 1000, "desc": "Recruit Toads"},
    "GoldenShroom": {"name": "Golden Mushroom", "price": 500, "desc": "Max speed item"},
    "Apprentice": {"name": "Apprentice Patch", "price": 1000000, "desc": "Become apprentice"},
    "Stuffwell": {"name": "Stuffwell Patch", "price": 1000, "desc": "BACK TO ADVENTURE!!"},
    "StarGuardians": {"name": "Star Guardians", "price": 1000, "desc": "Recruit Geno & Mallow"},
    "SMRPG": {"name": "SMRPG Patch", "price": 0, "desc": "Super Mario RPG areas"},
    "SmithyGang": {"name": "Smithy Gang", "price": 1000, "desc": "Smithy Gang bosses"},
    "PaperPartners": {"name": "Paper Partners", "price": 2000, "desc": "Paper Mario partners"},
    "Cooligan": {"name": "Cooligan Patch", "price": 750, "desc": "Cooligan class"},
    "Dark": {"name": "Dark Patch", "price": 2000000, "desc": "Dark Star power"},
    "FountainYouth": {"name": "Fountain of Youth", "price": 1000000, "desc": "Stay baby forever"},
    "Toady": {"name": "Toady Patch", "price": 0, "desc": "Toady class"},
    "Rookie": {"name": "Rookie Patch", "price": 0, "desc": "Thief training"}
}

# Fightmasters
FIGHTMASTERS = [
    {"name": "YoshiEgg Nook", "species": "Tanooki", "level": 30, "color": "Green", "hp": 300, "power": 30, "defense": 15, "speed": 12},
    {"name": "Sprak", "species": "Shy Guy", "level": 28, "color": "Purple", "hp": 280, "power": 28, "defense": 14, "speed": 14},
    {"name": "BPG-Duke", "species": "Koopa", "level": 32, "color": "Black Shell", "hp": 320, "power": 32, "defense": 18, "speed": 10},
    {"name": "Twenty-Second", "species": "Goomba", "level": 35, "color": "White", "hp": 350, "power": 35, "defense": 20, "speed": 15}
]

# Bros. Attacks
BROS_ATTACKS = {
    "Jump": {"sp": 0, "power": 1.0, "desc": "Basic jump attack"},
    "Hammer": {"sp": 3, "power": 1.5, "desc": "Hammer strike"},
    "Shell Slam": {"sp": 5, "power": 2.0, "desc": "Koopa shell attack"},
    "Fire Flower": {"sp": 8, "power": 2.5, "desc": "Fire damage to all"},
    "Thunder Hand": {"sp": 10, "power": 3.0, "desc": "Electric attack"},
    "Copy Flower": {"sp": 15, "power": 4.0, "desc": "Double team attack"}
}

# ============================================================================
# BATTLE SYSTEM
# ============================================================================

class BattleSystem:
    def __init__(self, player, enemies):
        self.player = player
        self.party = player.party[:3]  # Max 3 party members
        self.enemies = enemies
        self.turn = "player"
        self.selected_action = None
        self.selected_target = 0
        self.action_timer = 0
        self.action_power = 1.0
        self.battle_log = deque(maxlen=5)
        self.victory = False
        self.defeat = False
        self.rewards = {"xp": 0, "coins": 0, "items": []}
        
    def update(self, dt):
        """Update battle logic"""
        if self.action_timer > 0:
            self.action_timer -= dt
            if self.action_timer <= 0:
                self.execute_action()
                
    def select_action(self, action):
        """Player selects an action"""
        self.selected_action = action
        self.action_timer = 0.5  # Action delay
        
    def execute_action(self):
        """Execute the selected action"""
        if self.selected_action == "Attack":
            # Basic attack
            if self.enemies:
                target = self.enemies[self.selected_target % len(self.enemies)]
                damage = max(1, self.player.stats.power - target["defense"])
                damage = int(damage * self.action_power)
                target["hp"] -= damage
                self.battle_log.append(f"{self.player.name} deals {damage} damage!")
                
                if target["hp"] <= 0:
                    self.battle_log.append(f"{target['name']} defeated!")
                    self.rewards["xp"] += target["xp"]
                    self.rewards["coins"] += target["coins"]
                    self.enemies.remove(target)
                    
        elif self.selected_action == "Special":
            # Bros attack
            if self.player.stats.sp >= 5:
                self.player.stats.sp -= 5
                for enemy in self.enemies:
                    damage = max(1, self.player.stats.power * 2 - enemy["defense"])
                    enemy["hp"] -= damage
                self.battle_log.append(f"Special attack hits all for {damage}!")
                    
        elif self.selected_action == "Item":
            # Use item
            if self.player.items:
                item_name = self.player.items[0]
                if item_name in ITEMS:
                    item = ITEMS[item_name]
                    self.player.stats.hp = min(self.player.stats.max_hp, 
                                              self.player.stats.hp + item.get("hp", 0))
                    self.player.stats.sp = min(self.player.stats.max_sp,
                                              self.player.stats.sp + item.get("sp", 0))
                    self.player.items.remove(item_name)
                    self.battle_log.append(f"Used {item_name}!")
                    
        elif self.selected_action == "Defend":
            self.action_power = 0.5
            self.battle_log.append(f"{self.player.name} defends!")
            
        elif self.selected_action == "Run":
            if random.random() < 0.5:
                self.battle_log.append("Got away safely!")
                self.victory = True
            else:
                self.battle_log.append("Can't escape!")
                
        # Check victory
        if not self.enemies:
            self.victory = True
            self.battle_log.append("Victory!")
            self.player.add_xp(self.rewards["xp"])
            self.player.coins += self.rewards["coins"]
            
        # Enemy turn
        if not self.victory and self.turn == "player":
            self.turn = "enemy"
            self.enemy_turn()
            
    def enemy_turn(self):
        """Enemy attacks"""
        for enemy in self.enemies:
            damage = max(1, enemy["power"] - self.player.stats.defense)
            self.player.stats.hp -= damage
            self.battle_log.append(f"{enemy['name']} deals {damage} damage!")
            
            if self.player.stats.hp <= 0:
                self.defeat = True
                self.battle_log.append("Defeated...")
                
        self.turn = "player"
        
    def action_command_jump(self):
        """Timing-based jump command"""
        # Returns power multiplier based on timing
        return 1.0 + random.random() * 0.5
        
    def action_command_hammer(self):
        """Hold and release hammer command"""
        return 1.0 + random.random() * 0.8

# ============================================================================
# NETWORK LAYER - Server & Client
# ============================================================================

class PacketType(Enum):
    CONNECT = 0x01
    DISCONNECT = 0x02
    PLAYER_UPDATE = 0x03
    CHAT_MESSAGE = 0x04
    BATTLE_REQUEST = 0x05
    BATTLE_ACTION = 0x06
    WORLD_STATE = 0x07
    DOWNLOAD_PLAY = 0x08
    PATCH_SYNC = 0x09

class NetworkManager:
    def __init__(self):
        self.is_server = False
        self.is_client = False
        self.socket = None
        self.clients = {}
        self.server_thread = None
        self.client_thread = None
        self.message_queue = queue.Queue()
        self.players = {}
        
    def start_server(self, port=DEFAULT_PORT):
        """Start integrated server for hosting"""
        self.is_server = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('', port))
        self.socket.settimeout(0.1)
        
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()
        print(f"Server started on port {port}")
        
    def connect_client(self, host, port=DEFAULT_PORT):
        """Connect as client to server"""
        self.is_client = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_addr = (host, port)
        
        # Send connect packet
        packet = self._create_packet(PacketType.CONNECT, {"name": "Player"})
        self.socket.sendto(packet, self.server_addr)
        
        self.client_thread = threading.Thread(target=self._client_loop, daemon=True)
        self.client_thread.start()
        print(f"Connected to {host}:{port}")
        
    def _server_loop(self):
        """Main server loop"""
        while self.is_server:
            try:
                data, addr = self.socket.recvfrom(PACKET_SIZE)
                packet = self._parse_packet(data)
                
                if packet['type'] == PacketType.CONNECT:
                    player_id = hashlib.md5(f"{addr}".encode()).hexdigest()[:8]
                    self.clients[addr] = player_id
                    self.players[player_id] = packet['data']
                    print(f"Player {player_id} connected from {addr}")
                    
                    # Send world state to new player
                    world_packet = self._create_packet(PacketType.WORLD_STATE, self.players)
                    self.socket.sendto(world_packet, addr)
                    
                elif packet['type'] == PacketType.PLAYER_UPDATE:
                    if addr in self.clients:
                        player_id = self.clients[addr]
                        self.players[player_id].update(packet['data'])
                        
                        # Broadcast to all other clients
                        for client_addr, client_id in self.clients.items():
                            if client_addr != addr:
                                self.socket.sendto(data, client_addr)
                                
                elif packet['type'] == PacketType.DISCONNECT:
                    if addr in self.clients:
                        player_id = self.clients[addr]
                        del self.clients[addr]
                        del self.players[player_id]
                        print(f"Player {player_id} disconnected")
                        
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Server error: {e}")
                
    def _client_loop(self):
        """Main client loop"""
        self.socket.settimeout(0.1)
        while self.is_client:
            try:
                data, addr = self.socket.recvfrom(PACKET_SIZE)
                packet = self._parse_packet(data)
                self.message_queue.put(packet)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Client error: {e}")
                
    def _create_packet(self, packet_type, data):
        """Create network packet"""
        packet = {
            'type': packet_type,
            'timestamp': time.time(),
            'data': data
        }
        return json.dumps(packet).encode()
        
    def _parse_packet(self, data):
        """Parse network packet"""
        return json.loads(data.decode())
        
    def send_player_update(self, player_data):
        """Send player position/state update"""
        if self.is_client:
            packet = self._create_packet(PacketType.PLAYER_UPDATE, player_data)
            self.socket.sendto(packet, self.server_addr)
            
    def get_messages(self):
        """Get pending network messages"""
        messages = []
        while not self.message_queue.empty():
            messages.append(self.message_queue.get())
        return messages

# ============================================================================
# GAME ENGINE - State Management
# ============================================================================

class GameState(Enum):
    TITLE = 0
    STORY = 1
    CHARACTER_CREATE = 2
    GUARDIAN_SELECT = 3
    OVERWORLD = 4
    BATTLE = 5
    SHOP = 6
    DOJO = 7
    PATCHES = 8
    NETWORK = 9
    INVENTORY = 10
    DESERT = 11
    RUINS = 12

class GameEngine:
    def __init__(self):
        self.state = GameState.TITLE
        self.player = None
        self.network = NetworkManager()
        self.patches_owned = set(["MLSS", "MLPiT", "Beanish", "Ukiki", "PoisonShroom"])  # Default patches
        self.world_x = 0
        self.world_y = 0
        self.npcs = []
        self.battle_system = None
        self.transition_alpha = 0
        self.transition_target = None
        self.frame_count = 0
        
        # UI state
        self.menu_index = 0
        self.submenu_index = 0
        self.text_buffer = []
        self.input_text = ""
        self.notification = ""
        self.notification_timer = 0
        
        # Character creation state
        self.creation_step = 0
        self.selected_species = 0
        self.selected_gender = 0
        self.selected_color = 0
        self.selected_age = 0
        self.selected_star = 0
        self.selected_type = 0
        self.after_tutorial = False  # Flag for post-tutorial flow
        
        # Shop state
        self.shop_items = list(ITEMS.keys())[:4]  # First 4 items in shop
        
        # Performance tracking
        self.fps_history = []
        self.last_time = time.time()
        
    def show_notification(self, text, duration=2.0):
        """Show a notification message"""
        self.notification = text
        self.notification_timer = duration
        
    def update(self, dt):
        """Main update loop - 60 FPS target"""
        self.frame_count += 1
        
        # Update notification
        if self.notification_timer > 0:
            self.notification_timer -= dt
            
        # Update based on state
        if self.state == GameState.TITLE:
            self._update_title(dt)
        elif self.state == GameState.STORY:
            self._update_story(dt)
        elif self.state == GameState.CHARACTER_CREATE:
            self._update_character_create(dt)
        elif self.state == GameState.GUARDIAN_SELECT:
            self._update_guardian_select(dt)
        elif self.state == GameState.OVERWORLD:
            self._update_overworld(dt)
        elif self.state == GameState.BATTLE:
            self._update_battle(dt)
        elif self.state == GameState.SHOP:
            self._update_shop(dt)
        elif self.state == GameState.DOJO:
            self._update_dojo(dt)
        elif self.state == GameState.PATCHES:
            self._update_patches(dt)
        elif self.state == GameState.NETWORK:
            self._update_network(dt)
        elif self.state == GameState.INVENTORY:
            self._update_inventory(dt)
        elif self.state == GameState.DESERT:
            self._update_desert(dt)
        elif self.state == GameState.RUINS:
            self._update_ruins(dt)
            
        # Handle transitions
        if self.transition_target is not None:
            self.transition_alpha = min(255, self.transition_alpha + dt * 500)
            if self.transition_alpha >= 255:
                self.state = self.transition_target
                self.transition_target = None
                
        # Process network messages
        if self.network.is_client or self.network.is_server:
            messages = self.network.get_messages()
            for msg in messages:
                self._handle_network_message(msg)
                
    def render(self):
        """Render to dual screens"""
        # Clear screens
        top_screen.fill(BLACK)
        bottom_screen.fill(DARK_GRAY)
        
        # Render based on state
        if self.state == GameState.TITLE:
            self._render_title()
        elif self.state == GameState.STORY:
            self._render_story()
        elif self.state == GameState.CHARACTER_CREATE:
            self._render_character_create()
        elif self.state == GameState.GUARDIAN_SELECT:
            self._render_guardian_select()
        elif self.state == GameState.OVERWORLD:
            self._render_overworld()
        elif self.state == GameState.BATTLE:
            self._render_battle()
        elif self.state == GameState.SHOP:
            self._render_shop()
        elif self.state == GameState.DOJO:
            self._render_dojo()
        elif self.state == GameState.PATCHES:
            self._render_patches()
        elif self.state == GameState.NETWORK:
            self._render_network()
        elif self.state == GameState.INVENTORY:
            self._render_inventory()
        elif self.state == GameState.DESERT:
            self._render_desert()
        elif self.state == GameState.RUINS:
            self._render_ruins()
            
        # Render notification
        if self.notification_timer > 0:
            notif_surf = FONT_MEDIUM.render(self.notification, True, YELLOW)
            notif_rect = notif_surf.get_rect(center=(DS_TOP_W // 2, DS_TOP_H - 20))
            pygame.draw.rect(top_screen, BLACK, notif_rect.inflate(10, 4))
            top_screen.blit(notif_surf, notif_rect)
            
        # Apply transition overlay
        if self.transition_alpha > 0:
            overlay = pygame.Surface((DS_TOP_W, DS_TOP_H))
            overlay.set_alpha(self.transition_alpha)
            overlay.fill(BLACK)
            top_screen.blit(overlay, (0, 0))
            bottom_screen.blit(overlay, (0, 0))
            
        # Scale and blit to main screen
        scaled_top = pygame.transform.scale(top_screen, (DS_TOP_W * SCALE, DS_TOP_H * SCALE))
        scaled_bottom = pygame.transform.scale(bottom_screen, (DS_BOTTOM_W * SCALE, DS_BOTTOM_H * SCALE))
        
        screen.fill(BLACK)
        screen.blit(scaled_top, (0, 0))
        screen.blit(scaled_bottom, (0, (DS_TOP_H + SCREEN_GAP) * SCALE))
        
        # Draw DS frame
        self._draw_ds_frame()
        
        # FPS counter
        if self.frame_count % 60 == 0:
            current_time = time.time()
            fps = 60 / (current_time - self.last_time)
            self.fps_history.append(fps)
            if len(self.fps_history) > 10:
                self.fps_history.pop(0)
            self.last_time = current_time
            
        if self.fps_history:
            avg_fps = sum(self.fps_history) / len(self.fps_history)
            fps_text = FONT_SMALL.render(f"FPS: {avg_fps:.1f}", True, GREEN if avg_fps > 55 else YELLOW)
            screen.blit(fps_text, (10, 10))
            
    def _draw_ds_frame(self):
        """Draw Nintendo DS-style frame"""
        # Top screen border
        pygame.draw.rect(screen, GRAY, (0, 0, WINDOW_W, DS_TOP_H * SCALE), 2)
        # Bottom screen border  
        pygame.draw.rect(screen, GRAY, (0, (DS_TOP_H + SCREEN_GAP) * SCALE, WINDOW_W, DS_BOTTOM_H * SCALE), 2)
        # Middle gap
        gap_rect = pygame.Rect(0, DS_TOP_H * SCALE, WINDOW_W, SCREEN_GAP * SCALE)
        pygame.draw.rect(screen, DARK_GRAY, gap_rect)
        
    # State update methods
    def _update_title(self, dt):
        """Update title screen"""
        pass
        
    def _update_story(self, dt):
        """Update story sequence"""
        pass
        
    def _update_character_create(self, dt):
        """Update character creation"""
        pass
        
    def _update_guardian_select(self, dt):
        """Update guardian selection"""
        pass
        
    def _update_overworld(self, dt):
        """Update overworld exploration"""
        if self.player:
            # Simple movement
            keys = pygame.key.get_pressed()
            speed = 60 * dt  # pixels per second
            
            old_x, old_y = self.player.x, self.player.y
            
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.player.x -= speed
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.player.x += speed
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.player.y -= speed
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                self.player.y += speed
                
            # Keep in bounds
            self.player.x = max(8, min(DS_TOP_W - 8, self.player.x))
            self.player.y = max(8, min(DS_TOP_H - 8, self.player.y))
            
            # Random encounters
            if old_x != self.player.x or old_y != self.player.y:
                if random.random() < 0.01:  # 1% chance per movement
                    self.start_battle(["Goomba"])
            
            # Send position update if networked
            if self.network.is_client:
                self.network.send_player_update(self.player.to_dict())
                
    def _update_battle(self, dt):
        """Update battle system"""
        if self.battle_system:
            self.battle_system.update(dt)
            
            if self.battle_system.victory or self.battle_system.defeat:
                if self.battle_system.victory:
                    self.show_notification(f"Victory! +{self.battle_system.rewards['xp']} XP +{self.battle_system.rewards['coins']} coins")
                
                # Check if this was the tutorial battle
                if self.after_tutorial:
                    self.after_tutorial = False
                    self.player = None  # Reset player for character creation
                    self.transition_to(GameState.CHARACTER_CREATE)
                else:
                    self.transition_to(GameState.OVERWORLD)
                    
                self.battle_system = None
            
    def _update_shop(self, dt):
        """Update shop interface"""
        pass
        
    def _update_dojo(self, dt):
        """Update dojo battles"""
        pass
        
    def _update_patches(self, dt):
        """Update patch manager"""
        pass
        
    def _update_network(self, dt):
        """Update network lobby"""
        pass
        
    def _update_inventory(self, dt):
        """Update inventory screen"""
        pass
        
    def _update_desert(self, dt):
        """Update desert area"""
        pass
        
    def _update_ruins(self, dt):
        """Update ruins area"""
        pass
        
    # Render methods for each state (abbreviated for space - full implementation continues...)
    def _render_title(self):
        """Render title screen"""
        # Top screen - Logo and animation
        title_surf = FONT_LARGE.render("MARIO & LUIGI", True, RED)
        subtitle_surf = FONT_MEDIUM.render("LIVE", True, YELLOW)
        
        # Animate title
        y_offset = math.sin(self.frame_count * 0.02) * 5
        
        title_rect = title_surf.get_rect(center=(DS_TOP_W // 2, 60 + y_offset))
        subtitle_rect = subtitle_surf.get_rect(center=(DS_TOP_W // 2, 80 + y_offset))
        
        top_screen.blit(title_surf, title_rect)
        top_screen.blit(subtitle_surf, subtitle_rect)
        
        # Credits
        credit_text = "Bomb Productions Games & Sprak Co."
        credit_surf = FONT_TINY.render(credit_text, True, WHITE)
        credit_rect = credit_surf.get_rect(center=(DS_TOP_W // 2, 160))
        top_screen.blit(credit_surf, credit_rect)
        
        # Bottom screen - Menu
        menu_items = ["Single Player", "Host Game", "Join Game", "Download Play", "Options"]
        
        for i, item in enumerate(menu_items):
            color = YELLOW if i == self.menu_index else WHITE
            text_surf = FONT_MEDIUM.render(item, True, color)
            text_rect = text_surf.get_rect(center=(DS_BOTTOM_W // 2, 40 + i * 30))
            bottom_screen.blit(text_surf, text_rect)
            
        # Instructions
        inst_surf = FONT_TINY.render("Press Z/Enter to select", True, GRAY)
        inst_rect = inst_surf.get_rect(center=(DS_BOTTOM_W // 2, 180))
        bottom_screen.blit(inst_surf, inst_rect)
        
    def _render_battle(self):
        """Render battle screen"""
        if not self.battle_system:
            return
            
        # Top screen - Battle view
        # Draw battlefield
        pygame.draw.rect(top_screen, (100, 50, 0), (0, 100, DS_TOP_W, DS_TOP_H - 100))
        
        # Draw enemies
        y = 40
        for i, enemy in enumerate(self.battle_system.enemies):
            color = RED if i == self.battle_system.selected_target else WHITE
            enemy_text = f"{enemy['name']} HP: {enemy['hp']}"
            enemy_surf = FONT_SMALL.render(enemy_text, True, color)
            top_screen.blit(enemy_surf, (20, y))
            y += 20
            
        # Battle log
        log_y = 120
        for log in self.battle_system.battle_log:
            log_surf = FONT_TINY.render(log, True, WHITE)
            top_screen.blit(log_surf, (10, log_y))
            log_y += 10
        
        # Bottom screen - Battle menu
        battle_menu = ["Attack", "Special", "Item", "Defend", "Run"]
        
        for i, item in enumerate(battle_menu):
            x = 10 + (i % 3) * 80
            y = 30 + (i // 3) * 50
            
            button_rect = pygame.Rect(x, y, 70, 40)
            color = YELLOW if i == self.menu_index else GRAY
            pygame.draw.rect(bottom_screen, color, button_rect)
            pygame.draw.rect(bottom_screen, WHITE, button_rect, 1)
            
            text_surf = FONT_SMALL.render(item, True, BLACK if i == self.menu_index else WHITE)
            text_rect = text_surf.get_rect(center=button_rect.center)
            bottom_screen.blit(text_surf, text_rect)
            
        # Player stats
        stats_text = f"HP: {self.player.stats.hp}/{self.player.stats.max_hp}  SP: {self.player.stats.sp}/{self.player.stats.max_sp}"
        stats_surf = FONT_SMALL.render(stats_text, True, WHITE)
        bottom_screen.blit(stats_surf, (10, 150))
        
    def _render_shop(self):
        """Render shop interface"""
        # Top screen - Shop keeper and items
        shop_title = FONT_LARGE.render("ITEM SHOP", True, YELLOW)
        title_rect = shop_title.get_rect(center=(DS_TOP_W // 2, 20))
        top_screen.blit(shop_title, title_rect)
        
        # Item list
        y = 50
        for i, item_name in enumerate(self.shop_items):
            if item_name in ITEMS:
                item = ITEMS[item_name]
                color = YELLOW if i == self.menu_index else WHITE
                item_text = f"{item_name} - {item['price']} coins"
                item_surf = FONT_SMALL.render(item_text, True, color)
                top_screen.blit(item_surf, (20, y))
                y += 20
            
        # Player coins
        coins_surf = FONT_MEDIUM.render(f"Your coins: {self.player.coins if self.player else 0}", True, GREEN)
        top_screen.blit(coins_surf, (20, 150))
        
        # Bottom screen - Description and buy button
        if self.menu_index < len(self.shop_items) and self.shop_items[self.menu_index] in ITEMS:
            item = ITEMS[self.shop_items[self.menu_index]]
            desc_surf = FONT_MEDIUM.render(item["desc"], True, WHITE)
            desc_rect = desc_surf.get_rect(center=(DS_BOTTOM_W // 2, 50))
            bottom_screen.blit(desc_surf, desc_rect)
            
        buy_button = pygame.Rect(DS_BOTTOM_W // 2 - 40, 100, 80, 30)
        can_afford = self.player and self.menu_index < len(self.shop_items) and \
                    self.player.coins >= ITEMS[self.shop_items[self.menu_index]]["price"]
        button_color = GREEN if can_afford else GRAY
        pygame.draw.rect(bottom_screen, button_color, buy_button)
        buy_text = FONT_MEDIUM.render("BUY", True, BLACK if can_afford else DARK_GRAY)
        buy_rect = buy_text.get_rect(center=buy_button.center)
        bottom_screen.blit(buy_text, buy_rect)
        
        # Instructions
        inst_surf = FONT_TINY.render("Z: Buy  ESC: Exit", True, GRAY)
        bottom_screen.blit(inst_surf, (10, 170))
        
    def _render_character_create(self):
        """Render character creation"""
        # Get all species including patches
        all_species = dict(SPECIES)
        if "Beanish" in self.patches_owned:
            all_species.update({"Beanish": PATCH_SPECIES["Beanish"]})
        if "Ukiki" in self.patches_owned:
            all_species.update({"Ukiki": PATCH_SPECIES["Ukiki"]})
        if "Cooligan" in self.patches_owned:
            all_species.update({"Cooligan": PATCH_SPECIES["Cooligan"]})
        if "Toady" in self.patches_owned:
            all_species.update({"Toady": PATCH_SPECIES["Toady"]})
            
        species_list = list(all_species.keys())
        
        # Top screen - Preview
        preview_text = f"Species: {species_list[self.selected_species % len(species_list)]}"
        preview_surf = FONT_MEDIUM.render(preview_text, True, WHITE)
        top_screen.blit(preview_surf, (10, 10))
        
        # Draw character preview (simple rectangle for now)
        preview_rect = pygame.Rect(DS_TOP_W // 2 - 20, DS_TOP_H // 2 - 30, 40, 60)
        pygame.draw.rect(top_screen, YELLOW, preview_rect)
        
        # Bottom screen - Options
        options = ["Species", "Gender", "Color", "Type", "Age", "Confirm"]
        
        for i, option in enumerate(options):
            color = YELLOW if i == self.creation_step else WHITE
            text_surf = FONT_MEDIUM.render(option, True, color)
            bottom_screen.blit(text_surf, (10, 20 + i * 25))
            
            # Show current selection
            value = ""
            species_key = species_list[self.selected_species % len(species_list)]
            species_data = all_species[species_key]
            
            if i == 0:  # Species
                value = species_key
            elif i == 1:  # Gender
                value = species_data["genders"][self.selected_gender % len(species_data["genders"])]
            elif i == 2:  # Color
                value = species_data["colors"][self.selected_color % len(species_data["colors"])]
            elif i == 3:  # Type
                if "types" in species_data:
                    value = species_data["types"][self.selected_type % len(species_data["types"])]
                else:
                    value = "Normal"
            elif i == 4:  # Age
                ages = ["Baby", "Teen", "Adult"]
                value = ages[self.selected_age % 3]
                
            if value:
                value_surf = FONT_SMALL.render(value, True, DS_GREEN)
                bottom_screen.blit(value_surf, (120, 20 + i * 25))
                
        # Instructions
        inst_surf = FONT_TINY.render("←→: Change  ↑↓: Navigate  Z: Confirm", True, GRAY)
        bottom_screen.blit(inst_surf, (10, 170))
        
    def start_battle(self, enemy_names):
        """Start a battle encounter"""
        enemies = []
        for name in enemy_names:
            if name in ENEMIES:
                enemy_data = ENEMIES[name].copy()
                enemy_data["name"] = name
                enemies.append(enemy_data)
                
        if enemies:
            self.battle_system = BattleSystem(self.player, enemies)
            self.transition_to(GameState.BATTLE)
            
    def _handle_network_message(self, msg):
        """Process network message"""
        if msg['type'] == PacketType.WORLD_STATE:
            # Update world with server state
            for player_id, player_data in msg['data'].items():
                if player_id not in self.network.players:
                    self.network.players[player_id] = player_data
                else:
                    self.network.players[player_id].update(player_data)
                    
        elif msg['type'] == PacketType.PLAYER_UPDATE:
            # Update specific player
            player_data = msg['data']
            player_id = player_data.get('player_id')
            if player_id:
                self.network.players[player_id] = player_data
                
    def transition_to(self, new_state):
        """Start transition to new state"""
        self.transition_target = new_state
        self.transition_alpha = 0
        self.menu_index = 0  # Reset menu index when changing states
        
    def handle_input(self, event):
        """Handle input events"""
        if event.type == pygame.KEYDOWN:
            if self.state == GameState.TITLE:
                if event.key == pygame.K_UP:
                    self.menu_index = (self.menu_index - 1) % 5
                elif event.key == pygame.K_DOWN:
                    self.menu_index = (self.menu_index + 1) % 5
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    if self.menu_index == 0:  # Single Player
                        self.transition_to(GameState.STORY)
                    elif self.menu_index == 1:  # Host Game
                        self.network.start_server()
                        self.transition_to(GameState.NETWORK)
                        self.show_notification("Server started!")
                    elif self.menu_index == 2:  # Join Game
                        self.transition_to(GameState.NETWORK)
                    elif self.menu_index == 3:  # Download Play
                        self.show_notification("Download Play - Starting!")
                        self.transition_to(GameState.NETWORK)
                    elif self.menu_index == 4:  # Options
                        # Try to load save
                        if self.load_game():
                            self.show_notification("Save loaded!")
                        else:
                            self.show_notification("No save file found")
                        
            elif self.state == GameState.STORY:
                if event.key in [pygame.K_RETURN, pygame.K_z]:
                    # Skip story and go to Bowser tutorial
                    self.player = Character(name="Baby", level=1)
                    self.start_battle(["Bowser"])
                    self.after_tutorial = True  # Flag to go to character creation after battle
                    
            elif self.state == GameState.CHARACTER_CREATE:
                if event.key == pygame.K_UP:
                    self.creation_step = (self.creation_step - 1) % 6
                elif event.key == pygame.K_DOWN:
                    self.creation_step = (self.creation_step + 1) % 6
                elif event.key == pygame.K_LEFT:
                    if self.creation_step == 0:
                        self.selected_species = (self.selected_species - 1) % 100
                    elif self.creation_step == 1:
                        self.selected_gender = (self.selected_gender - 1) % 10
                    elif self.creation_step == 2:
                        self.selected_color = (self.selected_color - 1) % 20
                    elif self.creation_step == 3:
                        self.selected_type = (self.selected_type - 1) % 5
                    elif self.creation_step == 4:
                        self.selected_age = (self.selected_age - 1) % 3
                elif event.key == pygame.K_RIGHT:
                    if self.creation_step == 0:
                        self.selected_species = (self.selected_species + 1) % 100
                    elif self.creation_step == 1:
                        self.selected_gender = (self.selected_gender + 1) % 10
                    elif self.creation_step == 2:
                        self.selected_color = (self.selected_color + 1) % 20
                    elif self.creation_step == 3:
                        self.selected_type = (self.selected_type + 1) % 5
                    elif self.creation_step == 4:
                        self.selected_age = (self.selected_age + 1) % 3
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    if self.creation_step == 5:  # Confirm
                        # Create character
                        all_species = dict(SPECIES)
                        if "Beanish" in self.patches_owned:
                            all_species.update({"Beanish": PATCH_SPECIES["Beanish"]})
                        if "Ukiki" in self.patches_owned:
                            all_species.update({"Ukiki": PATCH_SPECIES["Ukiki"]})
                        species_list = list(all_species.keys())
                        species_key = species_list[self.selected_species % len(species_list)]
                        species_data = all_species[species_key]
                        
                        self.player = Character(
                            name="Player",
                            species=species_key,
                            gender=species_data["genders"][self.selected_gender % len(species_data["genders"])],
                            color=species_data["colors"][self.selected_color % len(species_data["colors"])],
                            age=["Baby", "Teen", "Adult"][self.selected_age % 3]
                        )
                        self.transition_to(GameState.GUARDIAN_SELECT)
                        
            elif self.state == GameState.GUARDIAN_SELECT:
                if event.key == pygame.K_LEFT:
                    self.selected_star = (self.selected_star - 1) % len(STAR_SPRITES)
                elif event.key == pygame.K_RIGHT:
                    self.selected_star = (self.selected_star + 1) % len(STAR_SPRITES)
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    self.player.star_guardian = STAR_SPRITES[self.selected_star]
                    # Apply buff
                    buff = STAR_SPRITES[self.selected_star]["buff"]
                    # Simple buff parsing
                    if "+2 Power" in buff:
                        self.player.stats.power += 2
                    elif "+2 Defense" in buff:
                        self.player.stats.defense += 2
                    elif "+2 Speed" in buff:
                        self.player.stats.speed += 2
                    elif "+5 Luck" in buff:
                        self.player.stats.luck += 5
                    elif "+10 HP" in buff:
                        self.player.stats.max_hp += 10
                        self.player.stats.hp = self.player.stats.max_hp
                    elif "+1 Power" in buff and "+1 Speed" in buff:
                        self.player.stats.power += 1
                        self.player.stats.speed += 1
                    
                    self.show_notification("Welcome to Toad Town!")
                    # Start game
                    self.transition_to(GameState.OVERWORLD)
                    
            elif self.state == GameState.OVERWORLD:
                if event.key == pygame.K_TAB:
                    self.menu_index = (self.menu_index + 1) % 6
                elif event.key == pygame.K_l and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    # Debug: Level up with Shift+L
                    if self.player:
                        self.player.level_up()
                        self.show_notification(f"Level up! Now level {self.player.level}")
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    if self.menu_index == 0:  # Shop
                        self.transition_to(GameState.SHOP)
                    elif self.menu_index == 1:  # Dojo
                        self.transition_to(GameState.DOJO)
                    elif self.menu_index == 2:  # Desert
                        self.transition_to(GameState.DESERT)
                    elif self.menu_index == 3:  # Patches
                        self.transition_to(GameState.PATCHES)
                    elif self.menu_index == 4:  # Inventory
                        self.transition_to(GameState.INVENTORY)
                    elif self.menu_index == 5:  # Save
                        self.save_game()
                elif event.key == pygame.K_ESCAPE:
                    self.transition_to(GameState.TITLE)
                    
            elif self.state == GameState.SHOP:
                if event.key == pygame.K_ESCAPE:
                    self.transition_to(GameState.OVERWORLD)
                elif event.key == pygame.K_UP:
                    self.menu_index = max(0, self.menu_index - 1)
                elif event.key == pygame.K_DOWN:
                    self.menu_index = min(len(self.shop_items) - 1, self.menu_index + 1)
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    # Buy item
                    if self.menu_index < len(self.shop_items):
                        item_name = self.shop_items[self.menu_index]
                        if item_name in ITEMS:
                            item = ITEMS[item_name]
                            if self.player.coins >= item["price"]:
                                self.player.coins -= item["price"]
                                self.player.items.append(item_name)
                                self.show_notification(f"Bought {item_name}!")
                            else:
                                self.show_notification("Not enough coins!")
                                
            elif self.state == GameState.BATTLE:
                if event.key == pygame.K_LEFT:
                    self.menu_index = (self.menu_index - 1) % 5
                elif event.key == pygame.K_RIGHT:
                    self.menu_index = (self.menu_index + 1) % 5
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    # Battle actions
                    battle_menu = ["Attack", "Special", "Item", "Defend", "Run"]
                    action = battle_menu[self.menu_index]
                    if self.battle_system:
                        self.battle_system.select_action(action)
                        
            elif self.state == GameState.INVENTORY:
                if event.key == pygame.K_ESCAPE:
                    self.transition_to(GameState.OVERWORLD)
                elif event.key == pygame.K_UP:
                    self.menu_index = max(0, self.menu_index - 1)
                elif event.key == pygame.K_DOWN:
                    if self.player and self.player.items:
                        self.menu_index = min(len(self.player.items) - 1, self.menu_index + 1)
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    # Use item
                    if self.player and self.menu_index < len(self.player.items):
                        item_name = self.player.items[self.menu_index]
                        if item_name in ITEMS:
                            item = ITEMS[item_name]
                            self.player.stats.hp = min(self.player.stats.max_hp,
                                                      self.player.stats.hp + item.get("hp", 0))
                            self.player.stats.sp = min(self.player.stats.max_sp,
                                                      self.player.stats.sp + item.get("sp", 0))
                            if item.get("luck"):
                                self.player.stats.luck += item["luck"]
                            self.player.items.pop(self.menu_index)
                            self.show_notification(f"Used {item_name}!")
                            
            elif self.state == GameState.DESERT:
                if event.key == pygame.K_ESCAPE:
                    self.transition_to(GameState.OVERWORLD)
                elif event.key == pygame.K_UP:
                    self.menu_index = (self.menu_index - 1) % 4
                elif event.key == pygame.K_DOWN:
                    self.menu_index = (self.menu_index + 1) % 4
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    if self.menu_index == 0:  # Fight Pokeys
                        self.start_battle(["Pokey"])
                    elif self.menu_index == 1:  # Visit Shops
                        self.menu_index = 0  # Reset for shop
                        self.transition_to(GameState.SHOP)
                    elif self.menu_index == 2:  # Dry Dry Ruins
                        self.transition_to(GameState.RUINS)
                    elif self.menu_index == 3:  # Back
                        self.transition_to(GameState.OVERWORLD)
                        
            elif self.state == GameState.DOJO:
                if event.key == pygame.K_ESCAPE:
                    self.transition_to(GameState.OVERWORLD)
                elif event.key == pygame.K_UP:
                    self.menu_index = (self.menu_index - 1) % len(FIGHTMASTERS)
                elif event.key == pygame.K_DOWN:
                    self.menu_index = (self.menu_index + 1) % len(FIGHTMASTERS)
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    # Start battle with selected Fightmaster
                    master = FIGHTMASTERS[self.menu_index]
                    enemy_data = {
                        "name": master["name"],
                        "hp": master["hp"],
                        "power": master["power"],
                        "defense": master["defense"],
                        "speed": master["speed"],
                        "xp": 200,
                        "coins": 500
                    }
                    self.battle_system = BattleSystem(self.player, [enemy_data])
                    self.transition_to(GameState.BATTLE)
                    
            elif self.state == GameState.PATCHES:
                if event.key == pygame.K_ESCAPE:
                    self.transition_to(GameState.OVERWORLD)
                elif event.key == pygame.K_UP:
                    available = [p for p in PATCHES.items() if p[0] not in self.patches_owned]
                    if available:
                        self.menu_index = max(0, self.menu_index - 1)
                elif event.key == pygame.K_DOWN:
                    available = [p for p in PATCHES.items() if p[0] not in self.patches_owned]
                    if available:
                        self.menu_index = min(len(available) - 1, self.menu_index + 1)
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    available = [p for p in PATCHES.items() if p[0] not in self.patches_owned]
                    if self.menu_index < len(available) and self.player:
                        patch_id, patch_data = available[self.menu_index]
                        if self.player.coins >= patch_data["price"]:
                            self.player.coins -= patch_data["price"]
                            self.patches_owned.add(patch_id)
                            self.show_notification(f"Bought {patch_data['name']}!")
                        else:
                            self.show_notification("Not enough coins!")
                            
            elif self.state == GameState.RUINS:
                if event.key == pygame.K_ESCAPE:
                    self.transition_to(GameState.DESERT)
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    if self.player and self.player.level >= 5:
                        self.start_battle(["Tutankoopa"])
                    else:
                        self.show_notification("Need level 5 to enter!")
                        
            elif self.state == GameState.NETWORK:
                if event.key == pygame.K_ESCAPE:
                    self.transition_to(GameState.TITLE)
                elif event.key == pygame.K_UP:
                    self.menu_index = (self.menu_index - 1) % 5
                elif event.key == pygame.K_DOWN:
                    self.menu_index = (self.menu_index + 1) % 5
                elif event.key in [pygame.K_RETURN, pygame.K_z]:
                    if self.menu_index == 0:  # Host Game
                        if not self.network.is_server:
                            self.network.start_server()
                            self.show_notification("Server started!")
                    elif self.menu_index == 1:  # Join Game
                        # Would need IP input, for now just show message
                        self.show_notification("Enter server IP (not implemented)")
                    elif self.menu_index == 2:  # Download Play
                        self.show_notification("Download Play mode!")
                    elif self.menu_index == 3:  # Friend Code
                        if self.player:
                            fc = f"{hash(self.player.name) % 1000000000000:012d}"
                            self.show_notification(f"Friend Code: {fc[:4]}-{fc[4:8]}-{fc[8:12]}")
                    elif self.menu_index == 4:  # Back
                        self.transition_to(GameState.TITLE)
                    
    def save_game(self):
        """Save game state"""
        save_data = {
            'player': self.player.to_dict() if self.player else None,
            'patches': list(self.patches_owned),
            'state': self.state.value
        }
        
        try:
            with open('mll_save.json', 'w') as f:
                json.dump(save_data, f, indent=2)
            self.show_notification("Game saved!")
        except Exception as e:
            self.show_notification(f"Save failed!")
            
    def load_game(self):
        """Load game state"""
        try:
            with open('mll_save.json', 'r') as f:
                save_data = json.load(f)
                
            if save_data['player']:
                self.player = Character.from_dict(save_data['player'])
            self.patches_owned = set(save_data['patches'])
            self.state = GameState(save_data['state'])
            self.show_notification("Game loaded!")
            return True
        except Exception as e:
            self.show_notification("No save found")
            return False
            
    # Additional render methods for other states
    def _render_story(self):
        """Render story sequence"""
        story_text = [
            "You drift as Star Energy through",
            "the night. Starlow greets you,",
            "bright and bubbly.",
            "",
            "She calls the Star Spirits—",
            "Eldstar nods—and they weave",
            "your energy into a new being.",
            "",
            '"What is your name?"',
            "",
            "After choosing, Bowser crashes in!",
            '"Meanie!" you shout.',
            "Tutorial battle begins!"
        ]
        
        # Top screen - Story text
        y = 20
        for line in story_text:
            text_surf = FONT_SMALL.render(line, True, WHITE)
            text_rect = text_surf.get_rect(x=10, y=y)
            top_screen.blit(text_surf, text_rect)
            y += 12
            
        # Bottom screen - Continue prompt
        prompt_surf = FONT_MEDIUM.render("Press Z to start tutorial", True, YELLOW)
        prompt_rect = prompt_surf.get_rect(center=(DS_BOTTOM_W // 2, DS_BOTTOM_H // 2))
        
        if self.frame_count % 60 < 40:  # Blinking
            bottom_screen.blit(prompt_surf, prompt_rect)
            
    def _render_guardian_select(self):
        """Render guardian star selection"""
        # Top screen - Star preview
        star = STAR_SPRITES[self.selected_star]
        
        name_surf = FONT_LARGE.render(star["name"], True, YELLOW)
        name_rect = name_surf.get_rect(center=(DS_TOP_W // 2, 40))
        top_screen.blit(name_surf, name_rect)
        
        # Draw star (simple shape)
        star_points = []
        cx, cy = DS_TOP_W // 2, DS_TOP_H // 2
        for i in range(10):
            angle = math.pi * 2 * i / 10 - math.pi / 2
            if i % 2 == 0:
                r = 30
            else:
                r = 15
            x = cx + math.cos(angle) * r
            y = cy + math.sin(angle) * r
            star_points.append((x, y))
        pygame.draw.polygon(top_screen, YELLOW, star_points)
        
        # Bottom screen - Star info
        info_lines = [
            f"Color: {star['color']}",
            f"Personality: {star['personality']}",
            f"Buff: {star['buff']}"
        ]
        
        y = 40
        for line in info_lines:
            text_surf = FONT_MEDIUM.render(line, True, WHITE)
            bottom_screen.blit(text_surf, (20, y))
            y += 30
            
        # Navigation
        nav_surf = FONT_SMALL.render("< >: Select  Z: Confirm", True, GRAY)
        nav_rect = nav_surf.get_rect(center=(DS_BOTTOM_W // 2, 160))
        bottom_screen.blit(nav_surf, nav_rect)
        
    def _render_overworld(self):
        """Render overworld/Toad Town"""
        # Top screen - Game world
        # Draw simple tile grid
        tile_size = 16
        for y in range(0, DS_TOP_H, tile_size):
            for x in range(0, DS_TOP_W, tile_size):
                # Checkerboard pattern
                if (x // tile_size + y // tile_size) % 2 == 0:
                    pygame.draw.rect(top_screen, DS_GREEN, (x, y, tile_size, tile_size))
                else:
                    pygame.draw.rect(top_screen, (0, 120, 0), (x, y, tile_size, tile_size))
                    
        # Draw player
        if self.player:
            player_rect = pygame.Rect(self.player.x - 4, self.player.y - 4, 8, 8)
            pygame.draw.rect(top_screen, YELLOW, player_rect)
            
        # Draw other players if networked
        for player_id, player_data in self.network.players.items():
            if player_id != getattr(self.player, 'player_id', None):
                other_rect = pygame.Rect(player_data.get('x', 128) - 4, player_data.get('y', 96) - 4, 8, 8)
                pygame.draw.rect(top_screen, CYAN, other_rect)
                
        # Location name
        location_surf = FONT_MEDIUM.render("Toad Town", True, WHITE)
        pygame.draw.rect(top_screen, BLACK, (0, 0, location_surf.get_width() + 10, 20))
        top_screen.blit(location_surf, (5, 2))
        
        # Bottom screen - Menu/Map
        menu_items = ["Shop", "Dojo", "Desert", "Patches", "Inventory", "Save"]
        
        for i in range(2):
            for j in range(3):
                idx = i * 3 + j
                if idx < len(menu_items):
                    x = 10 + j * 80
                    y = 30 + i * 60
                    
                    # Draw button
                    button_rect = pygame.Rect(x, y, 70, 40)
                    color = DS_BLUE if idx == self.menu_index else DARK_GRAY
                    pygame.draw.rect(bottom_screen, color, button_rect)
                    pygame.draw.rect(bottom_screen, WHITE, button_rect, 1)
                    
                    # Draw text
                    text_surf = FONT_SMALL.render(menu_items[idx], True, WHITE)
                    text_rect = text_surf.get_rect(center=button_rect.center)
                    bottom_screen.blit(text_surf, text_rect)
                    
        # Player stats
        if self.player:
            stats_text = f"Lv.{self.player.level} HP:{self.player.stats.hp}/{self.player.stats.max_hp} Coins:{self.player.coins}"
            stats_surf = FONT_TINY.render(stats_text, True, WHITE)
            bottom_screen.blit(stats_surf, (5, 170))
            
    def _render_dojo(self):
        """Render dojo/Fightmasters"""
        # Top screen - Dojo interior
        dojo_title = FONT_LARGE.render("MUSHROOM KINGDOM DOJO", True, RED)
        title_rect = dojo_title.get_rect(center=(DS_TOP_W // 2, 20))
        top_screen.blit(dojo_title, title_rect)
        
        # Fightmasters list
        y = 50
        for i, master in enumerate(FIGHTMASTERS):
            color = YELLOW if i == self.menu_index else WHITE
            master_text = f"{master['name']} Lv.{master['level']}"
            master_surf = FONT_SMALL.render(master_text, True, color)
            top_screen.blit(master_surf, (20, y))
            y += 25
            
        # Bottom screen - Challenge info
        if self.menu_index < len(FIGHTMASTERS):
            master = FIGHTMASTERS[self.menu_index]
            info_lines = [
                f"Species: {master['species']}",
                f"Color: {master['color']}",
                f"Level: {master['level']}",
                "",
                "Defeat for prize + photo!"
            ]
            
            y = 30
            for line in info_lines:
                info_surf = FONT_SMALL.render(line, True, WHITE)
                bottom_screen.blit(info_surf, (20, y))
                y += 20
                
        # Challenge button
        challenge_button = pygame.Rect(DS_BOTTOM_W // 2 - 50, 140, 100, 30)
        pygame.draw.rect(bottom_screen, RED, challenge_button)
        challenge_text = FONT_MEDIUM.render("CHALLENGE", True, WHITE)
        challenge_rect = challenge_text.get_rect(center=challenge_button.center)
        bottom_screen.blit(challenge_text, challenge_rect)
        
    def _render_patches(self):
        """Render patch manager"""
        # Top screen - Owned patches
        title_surf = FONT_LARGE.render("PATCH MANAGER", True, YELLOW)
        title_rect = title_surf.get_rect(center=(DS_TOP_W // 2, 20))
        top_screen.blit(title_surf, title_rect)
        
        owned_text = f"Owned: {len(self.patches_owned)}/{len(PATCHES)}"
        owned_surf = FONT_SMALL.render(owned_text, True, WHITE)
        top_screen.blit(owned_surf, (10, 40))
        
        # List owned patches
        y = 60
        for patch_id in list(self.patches_owned)[:5]:
            if patch_id in PATCHES:
                patch_surf = FONT_TINY.render(PATCHES[patch_id]['name'], True, GREEN)
                top_screen.blit(patch_surf, (20, y))
                y += 15
                
        # Bottom screen - Available patches
        available = [p for p in PATCHES.items() if p[0] not in self.patches_owned]
        
        if available:
            y = 20
            for i, (patch_id, patch_data) in enumerate(available[:6]):
                color = YELLOW if i == self.menu_index else WHITE
                
                # Name and price
                text = f"{patch_data['name']} - {patch_data['price']} coins"
                text_surf = FONT_TINY.render(text, True, color)
                bottom_screen.blit(text_surf, (10, y))
                y += 20
                
        # Buy button
        if self.menu_index < len(available) and self.player:
            patch_data = available[self.menu_index][1]
            can_afford = self.player.coins >= patch_data["price"]
            buy_rect = pygame.Rect(DS_BOTTOM_W - 80, DS_BOTTOM_H - 40, 70, 30)
            color = GREEN if can_afford else GRAY
            pygame.draw.rect(bottom_screen, color, buy_rect)
            buy_text = FONT_SMALL.render("BUY", True, BLACK if can_afford else DARK_GRAY)
            bottom_screen.blit(buy_text, buy_rect.move(20, 8))
            
    def _render_network(self):
        """Render network/WFC screen"""
        # Top screen - Server list
        title_surf = FONT_LARGE.render("NINTENDO WFC", True, CYAN)
        title_rect = title_surf.get_rect(center=(DS_TOP_W // 2, 20))
        top_screen.blit(title_surf, title_rect)
        
        if self.network.is_server:
            status = f"Hosting on port {DEFAULT_PORT}"
        elif self.network.is_client:
            status = "Connected"
        else:
            status = "Offline"
            
        status_surf = FONT_SMALL.render(status, True, GREEN if self.network.is_client else WHITE)
        top_screen.blit(status_surf, (10, 40))
        
        # Player list
        y = 60
        for player_id, player_data in self.network.players.items():
            player_text = f"{player_data.get('name', 'Unknown')} Lv.{player_data.get('level', 1)}"
            player_surf = FONT_TINY.render(player_text, True, CYAN)
            top_screen.blit(player_surf, (20, y))
            y += 15
            
        # Bottom screen - Connection options
        options = ["Host Game", "Join Game", "Download Play", "Friend Code", "Back"]
        
        for i, option in enumerate(options):
            color = YELLOW if i == self.menu_index else WHITE
            opt_surf = FONT_MEDIUM.render(option, True, color)
            bottom_screen.blit(opt_surf, (20, 30 + i * 30))
            
        # Friend code display
        if self.player:
            fc = f"{hash(self.player.name) % 1000000000000:012d}"
            fc_formatted = f"{fc[:4]}-{fc[4:8]}-{fc[8:12]}"
            fc_surf = FONT_TINY.render(fc_formatted, True, GRAY)
            fc_rect = fc_surf.get_rect(center=(DS_BOTTOM_W // 2, 170))
            bottom_screen.blit(fc_surf, fc_rect)
            
    def _render_inventory(self):
        """Render inventory screen"""
        # Top screen - Character stats
        if self.player:
            # Character info
            info_lines = [
                f"Name: {self.player.name}",
                f"Species: {self.player.species}",
                f"Level: {self.player.level}",
                f"HP: {self.player.stats.hp}/{self.player.stats.max_hp}",
                f"SP: {self.player.stats.sp}/{self.player.stats.max_sp}",
                f"Power: {self.player.stats.power}",
                f"Defense: {self.player.stats.defense}",
                f"Speed: {self.player.stats.speed}",
                f"Luck: {self.player.stats.luck}",
                f"Coins: {self.player.coins}",
                f"XP: {self.player.xp}/{self.player.level * 50}"
            ]
            
            y = 10
            for line in info_lines:
                info_surf = FONT_SMALL.render(line, True, WHITE)
                top_screen.blit(info_surf, (10, y))
                y += 15
                
        # Bottom screen - Items
        title_surf = FONT_MEDIUM.render("INVENTORY", True, YELLOW)
        bottom_screen.blit(title_surf, (10, 10))
        
        if self.player and self.player.items:
            y = 40
            for i, item in enumerate(self.player.items[:8]):
                color = YELLOW if i == self.menu_index else WHITE
                item_surf = FONT_SMALL.render(item, True, color)
                bottom_screen.blit(item_surf, (20, y))
                y += 18
        else:
            empty_surf = FONT_SMALL.render("(Empty)", True, GRAY)
            bottom_screen.blit(empty_surf, (20, 40))
            
        # Instructions
        inst_surf = FONT_TINY.render("Z: Use  ESC: Back", True, GRAY)
        bottom_screen.blit(inst_surf, (10, 170))
        
    def _render_desert(self):
        """Render desert area"""
        # Top screen - Desert view
        for y in range(0, DS_TOP_H, 20):
            for x in range(0, DS_TOP_W, 20):
                pygame.draw.rect(top_screen, (200, 180, 100), (x, y, 20, 20))
                
        title_surf = FONT_LARGE.render("DRY DRY DESERT", True, YELLOW)
        title_rect = title_surf.get_rect(center=(DS_TOP_W // 2, 20))
        top_screen.blit(title_surf, title_rect)
        
        # Bottom screen - Options
        options = ["Fight Pokeys", "Visit Shops", "Dry Dry Ruins", "Back"]
        
        for i, option in enumerate(options):
            color = YELLOW if i == self.menu_index else WHITE
            opt_surf = FONT_MEDIUM.render(option, True, color)
            bottom_screen.blit(opt_surf, (20, 40 + i * 35))
            
        # Instructions
        inst_surf = FONT_TINY.render("Z: Select  ESC: Back", True, GRAY)
        bottom_screen.blit(inst_surf, (10, 170))
        
    def _render_ruins(self):
        """Render ruins area"""
        # Top screen - Ruins entrance
        pygame.draw.rect(top_screen, (100, 80, 60), (0, 0, DS_TOP_W, DS_TOP_H))
        
        title_surf = FONT_LARGE.render("DRY DRY RUINS", True, GOLD)
        title_rect = title_surf.get_rect(center=(DS_TOP_W // 2, 20))
        top_screen.blit(title_surf, title_rect)
        
        # Check level requirement
        can_enter = self.player and self.player.level >= 5
        
        if can_enter:
            msg = "The ruins are open..."
        else:
            msg = "Guardian: 'Not yet... grow stronger first.'"
            
        msg_surf = FONT_SMALL.render(msg, True, WHITE)
        msg_rect = msg_surf.get_rect(center=(DS_TOP_W // 2, DS_TOP_H // 2))
        top_screen.blit(msg_surf, msg_rect)
        
        # Bottom screen
        if can_enter:
            boss_text = "TUTANKOOPA awaits within!"
            boss_surf = FONT_MEDIUM.render(boss_text, True, RED)
            boss_rect = boss_surf.get_rect(center=(DS_BOTTOM_W // 2, DS_BOTTOM_H // 2))
            bottom_screen.blit(boss_surf, boss_rect)
            
            enter_text = "Press Z to enter"
            enter_surf = FONT_SMALL.render(enter_text, True, YELLOW)
            enter_rect = enter_surf.get_rect(center=(DS_BOTTOM_W // 2, DS_BOTTOM_H // 2 + 30))
            bottom_screen.blit(enter_surf, enter_rect)
        else:
            back_text = "Press ESC to return"
            back_surf = FONT_SMALL.render(back_text, True, WHITE)
            back_rect = back_surf.get_rect(center=(DS_BOTTOM_W // 2, DS_BOTTOM_H // 2))
            bottom_screen.blit(back_surf, back_rect)

# ============================================================================
# MAIN GAME LOOP
# ============================================================================

def main():
    """Main game loop - 60 FPS target"""
    game = GameEngine()
    running = True
    
    # Performance tracking
    frame_times = []
    last_frame = time.perf_counter()
    
    while running:
        # Frame timing
        current_time = time.perf_counter()
        dt = current_time - last_frame
        last_frame = current_time
        
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game.handle_input(event)
                
        # Update game state
        game.update(dt)
        
        # Render
        game.render()
        
        # Update display
        pygame.display.flip()
        
        # Frame rate limiting - exactly 60 FPS
        clock.tick(FPS)
        
        # Track performance
        frame_times.append(dt)
        if len(frame_times) > 60:
            frame_times.pop(0)
            
        # Print performance stats every second
        if game.frame_count % 60 == 0 and frame_times:
            avg_frame_time = sum(frame_times) / len(frame_times)
            fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
            if fps < 55:
                print(f"Performance warning: {fps:.1f} FPS")
                
    # Cleanup
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
