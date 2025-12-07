import disnake
from disnake.ext import commands
import aiohttp
import re
from typing import Optional


def translate_time(text: str) -> str:
    if not text or not isinstance(text, str):
        return text
    
    translations = {
        'hours': 'часов',
        'hour': 'час',
        'minutes': 'минут',
        'minute': 'минута',
        'seconds': 'секунд',
        'second': 'секунда',
        'days': 'дней',
        'day': 'день',
        'weeks': 'недель',
        'week': 'неделя',
        'months': 'месяцев',
        'month': 'месяц',
        'years': 'лет',
        'year': 'год',
        'miles': 'миль',
        'mile': 'миля',
        'kilometers': 'км',
        'kilometer': 'км',
        'and': 'и',
        'ago': 'назад',
    }
    
    result = text
    for eng, rus in translations.items():
        result = re.sub(rf'\b{eng}\b', rus, result, flags=re.IGNORECASE)
    
    return result


def format_value(value) -> str:
    """Форматирование значения с переводом"""
    if value is None:
        return "N/A"
    if isinstance(value, str):
        return translate_time(value)
    return str(value)


def stat_line(emoji: str, label: str, value) -> str:
    """Форматирование строки статистики: `emoji` label: **value**"""
    return f"`{emoji}` {label}: **{format_value(value)}**"


class StatsView(disnake.ui.View):
    """View с кнопками для навигации по статистике"""
    
    def __init__(self, data: dict, author_id: int):
        super().__init__(timeout=None)
        self.data = data
        self.author_id = author_id
        self.current_page = "overview"
        self.update_buttons()
        
    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        """Проверка что только автор может использовать кнопки"""
        if inter.author.id != self.author_id:
            await inter.response.send_message(
                "❌ Только автор команды может использовать эти кнопки!", 
                ephemeral=True
            )
            return False
        return True
    
    def update_buttons(self):
        """Обновить состояние кнопок - отключить текущую страницу"""
        button_mapping = {
            "overview": 0,
            "kills": 1,
            "combat": 2,
            "deaths": 3,
            "gathered": 4,
            "building": 5,
            "exposure": 6,
            "fishing": 7,
            "other": 8,
        }
        
        for item in self.children:
            if isinstance(item, disnake.ui.Button):
                item.disabled = False
        
        current_index = button_mapping.get(self.current_page)
        if current_index is not None and current_index < len(self.children):
            self.children[current_index].disabled = True
    
    def get_base_embed(self) -> disnake.Embed:
        """Базовый embed с информацией о профиле"""
        embed = disnake.Embed(color=0xCD412B)
        embed.set_author(
            name=self.data.get("personaname", "Unknown"),
            icon_url=self.data.get("avatar_url", ""),
            url=f"https://steamcommunity.com/profiles/{self.data.get('steamid', '')}"
        )
        embed.set_thumbnail(url=self.data.get("avatar_full_url", ""))
        
        if self.data.get("is_private"):
            embed.description = "🔒 **Профиль приватный** — данные могут быть устаревшими"
        
        # Статус в footer
        status = []
        if self.data.get("is_banned"):
            status.append("🔨 ЗАБАНЕН")
        if self.data.get("is_private"):
            status.append("🔒 Приватный")
        else:
            status.append("🔓 Открытый")
        
        since_update = format_value(self.data.get("since_last_update", ""))
        
        embed.set_footer(
            text=f"{' | '.join(status)} • SteamID: {self.data.get('steamid', 'N/A')} • Обновлено: {since_update} назад"
        )
        return embed
    
    def get_overview_embed(self) -> disnake.Embed:
        """Обзор профиля"""
        embed = self.get_base_embed()
        embed.title = "📊 Обзор профиля"
        
        overview = self.data.get("overview", {})
        pvp = self.data.get("pvp_stats", {})
        
        embed.add_field(
            name="⏱️ Время в игре",
            value=f"```{format_value(overview.get('time_played'))}```",
            inline=True
        )
        embed.add_field(
            name="📅 Аккаунт создан",
            value=f"```{format_value(overview.get('account_created'))}```",
            inline=True
        )
        embed.add_field(
            name="🎮 За 2 недели",
            value=f"```{format_value(overview.get('played_last_2weeks'))}```",
            inline=True
        )
        
        embed.add_field(
            name="⚔️ K/D Ratio",
            value=f"```{format_value(pvp.get('kdr'))}```",
            inline=True
        )
        embed.add_field(
            name="💀 Убийства / Смерти",
            value=f"```{format_value(pvp.get('kills'))} / {format_value(pvp.get('deaths'))}```",
            inline=True
        )
        embed.add_field(
            name="🎯 Точность",
            value=f"```{format_value(pvp.get('bullets_hit_percent'))}```",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Хедшоты",
            value=f"```{format_value(pvp.get('headshots'))} ({format_value(pvp.get('headshot_percent'))})```",
            inline=True
        )
        embed.add_field(
            name="🔫 Выстрелов / Попаданий",
            value=f"```{format_value(pvp.get('bullets_fired'))} / {format_value(pvp.get('bullets_hit'))}```",
            inline=True
        )
        embed.add_field(
            name="🏆 Достижения",
            value=f"```{format_value(overview.get('achievement_count'))}```",
            inline=True
        )
        
        return embed
    
    def get_kills_embed(self) -> disnake.Embed:
        """Статистика убийств"""
        embed = self.get_base_embed()
        embed.title = "💀 Статистика убийств"
        
        kills = self.data.get("kills", {})
        
        creatures = "\n".join([
            stat_line("🧑", "Игроки", kills.get('players')),
            stat_line("🔬", "Ученые", kills.get('scientists')),
            stat_line("🐻", "Медведи", kills.get('bears')),
            stat_line("🐗", "Кабаны", kills.get('boars')),
            stat_line("🐺", "Волки", kills.get('wolves')),
            stat_line("🦌", "Олени", kills.get('deer')),
            stat_line("🐴", "Лошади", kills.get('horses')),
            stat_line("🐔", "Куры", kills.get('chickens')),
        ])
        embed.add_field(name="🎯 Убийства существ", value=creatures, inline=True)
        
        other = self.data.get("other", {})
        other_kills = "\n".join([
            stat_line("🚀", "MLRS убийств", other.get('mlrs_kills')),
            stat_line("🦈", "Из гарпуна", other.get('shark_speargun_kills')),
            stat_line("🛢️", "Бочек", other.get('barrels_destroyed')),
            stat_line("🚗", "Машин", other.get('cars_shredded')),
        ])
        embed.add_field(name="💥 Другое", value=other_kills, inline=True)
        
        melee = self.data.get("melee", {})
        melee_stats = "\n".join([
            stat_line("🗡️", "Ударов", melee.get('strikes')),
            stat_line("🪃", "Бросков", melee.get('throws')),
        ])
        embed.add_field(name="⚔️ Ближний бой", value=melee_stats, inline=False)
        
        return embed
    
    def get_combat_embed(self) -> disnake.Embed:
        """Боевая статистика"""
        embed = self.get_base_embed()
        embed.title = "🔫 Боевая статистика"
        
        bullets = self.data.get("bullets_hit", {})
        bow = self.data.get("bow_hits", {})
        shotgun = self.data.get("shotgun_hits", {})
        
        bullet_stats = "\n".join([
            stat_line("🧑", "В игроков", bullets.get('players')),
            stat_line("🏠", "В строения", bullets.get('buildings')),
            stat_line("💀", "В трупы", bullets.get('dead_players')),
            stat_line("🐻", "В медведей", bullets.get('bears')),
            stat_line("🐗", "В кабанов", bullets.get('boars')),
            stat_line("🐺", "В волков", bullets.get('wolves')),
            stat_line("🐴", "В лошадей", bullets.get('horses')),
        ])
        embed.add_field(name="🔫 Попадания пулями", value=bullet_stats, inline=True)
        
        bow_stats = "\n".join([
            stat_line("🎯", "Точность", bow.get('rate')),
            stat_line("🧑", "В игроков", bow.get('players')),
            stat_line("🏠", "В строения", bow.get('buildings')),
            stat_line("🐻", "В медведей", bow.get('bears')),
            stat_line("🦌", "В оленей", bow.get('deer')),
            stat_line("🏹", "Выстрелов", bow.get('shots_fired')),
        ])
        embed.add_field(name="🏹 Лук", value=bow_stats, inline=True)
        
        shotgun_stats = "\n".join([
            stat_line("🧑", "В игроков", shotgun.get('players')),
            stat_line("🏠", "В строения", shotgun.get('buildings')),
            stat_line("🔫", "Выстрелов", shotgun.get('shots_fired')),
        ])
        embed.add_field(name="💥 Дробовик", value=shotgun_stats, inline=True)
        
        other = self.data.get("other", {})
        embed.add_field(
            name="🚀 Ракеты выпущено", 
            value=f"```{format_value(other.get('rockets_fired'))}```", 
            inline=False
        )
        
        return embed
    
    def get_deaths_embed(self) -> disnake.Embed:
        """Статистика смертей и ранений"""
        embed = self.get_base_embed()
        embed.title = "☠️ Смерти и ранения"
        
        deaths = self.data.get("deaths", {})
        wounds = self.data.get("wounds", {})
        
        death_stats = "\n".join([
            stat_line("💀", "Всего смертей", deaths.get('total')),
            stat_line("🪂", "От падения", deaths.get('fall')),
            stat_line("🔫", "Суицид", deaths.get('suicide')),
            stat_line("💥", "Самоповреждение", deaths.get('self_inflicted')),
        ])
        embed.add_field(name="💀 Смерти", value=death_stats, inline=True)
        
        wound_stats = "\n".join([
            stat_line("🩸", "Ранен", wounds.get('wounded')),
            stat_line("💊", "Исцелён", wounds.get('healed')),
            stat_line("🤝", "Помог другим", wounds.get('assisted')),
        ])
        embed.add_field(name="🩹 Ранения", value=wound_stats, inline=True)
        
        return embed
    
    def get_gathered_embed(self) -> disnake.Embed:
        """Статистика добычи ресурсов"""
        embed = self.get_base_embed()
        embed.title = "⛏️ Добыча ресурсов"
        
        gathered = self.data.get("gathered", {})
        consumed = self.data.get("consumed", {})
        
        resources = "\n".join([
            stat_line("🪵", "Дерево", gathered.get('wood')),
            stat_line("🪨", "Камень", gathered.get('stone')),
            stat_line("⛏️", "Металл", gathered.get('metal_ore')),
            stat_line("🔩", "Скрап", gathered.get('scrap')),
            stat_line("🧵", "Ткань", gathered.get('cloth')),
            stat_line("🛢️", "НК топливо", gathered.get('low_grade_fuel')),
            stat_line("🐄", "Кожа", gathered.get('leather')),
        ])
        embed.add_field(name="📦 Ресурсы", value=resources, inline=True)
        
        hits = "\n".join([
            stat_line("⛏️", "Ударов по руде", gathered.get('ore_hits')),
            stat_line("🪓", "Ударов по дереву", gathered.get('tree_hits')),
        ])
        embed.add_field(name="🔨 Добыча", value=hits, inline=True)
        
        consumption = "\n".join([
            stat_line("💧", "Воды выпито", consumed.get('water')),
            stat_line("🍖", "Калорий съедено", consumed.get('calories')),
        ])
        embed.add_field(name="🍽️ Потребление", value=consumption, inline=False)
        
        return embed
    
    def get_building_embed(self) -> disnake.Embed:
        """Статистика строительства"""
        embed = self.get_base_embed()
        embed.title = "🏗️ Строительство и электричество"
        
        building = self.data.get("building_blocks", {})
        other = self.data.get("other", {})
        
        build_stats = "\n".join([
            stat_line("🧱", "Блоков установлено", building.get('placed')),
            stat_line("⬆️", "Блоков улучшено", building.get('upgraded')),
        ])
        embed.add_field(name="🏠 Строительство", value=build_stats, inline=True)
        
        electric_stats = "\n".join([
            stat_line("🔌", "Проводов", other.get('wires_connected')),
            stat_line("🔧", "Труб", other.get('pipes_connected')),
            stat_line("🔔", "Сигнализаций", other.get('tincanalarms_wired')),
        ])
        embed.add_field(name="⚡ Электричество", value=electric_stats, inline=True)
        
        embed.add_field(
            name="📜 Чертежей изучено", 
            value=f"```{format_value(other.get('bps_learned'))}```", 
            inline=False
        )
        
        return embed
    
    def get_exposure_embed(self) -> disnake.Embed:
        """Статистика окружающей среды"""
        embed = self.get_base_embed()
        embed.title = "🌡️ Окружающая среда"
        
        exposure = self.data.get("exposure", {})
        horse = self.data.get("horse_distance_ridden", {})
        other = self.data.get("other", {})
        
        temp_stats = "\n".join([
            stat_line("❄️", "На холоде", exposure.get('cold')),
            stat_line("🔥", "На жаре", exposure.get('heat')),
            stat_line("😌", "В комфорте", exposure.get('comfort')),
            stat_line("☢️", "В радиации", exposure.get('radiation')),
        ])
        embed.add_field(name="🌡️ Температура", value=temp_stats, inline=True)
        
        transport = "\n".join([
            stat_line("🐴", "На лошади", f"{format_value(horse.get('kilometers'))} км"),
            stat_line("🏇", "Раз садился", horse.get('mounted_times')),
            stat_line("🚁", "Посадок на вертолётную", other.get('helipad_landings')),
            stat_line("🛶", "На каяке", other.get('kayak_distance_travelled')),
        ])
        embed.add_field(name="🚗 Транспорт", value=transport, inline=True)
        
        return embed
    
    def get_other_embed(self) -> disnake.Embed:
        """Другая статистика"""
        embed = self.get_base_embed()
        embed.title = "📋 Другое"
        
        other = self.data.get("other", {})
        menus = self.data.get("menus_opened", {})
        instruments = self.data.get("instruments", {})
        
        menu_stats = "\n".join([
            stat_line("🎒", "Инвентарь", menus.get('inventory')),
            stat_line("🗺️", "Карта", menus.get('map')),
            stat_line("🔨", "Крафт", menus.get('crafting')),
            stat_line("🏠", "Шкаф", menus.get('cupboard')),
        ])
        embed.add_field(name="📂 Открытий меню", value=menu_stats, inline=True)
        
        misc_stats = "\n".join([
            stat_line("🎤", "Голосовой чат", other.get('voicechat_time')),
            stat_line("👋", "Помахал игрокам", other.get('waved_at_players')),
            stat_line("📦", "Выброшено", other.get('items_dropped')),
            stat_line("🔍", "Осмотрено", other.get('items_inspected')),
            stat_line("📋", "Миссий", other.get('missions_completed')),
            stat_line("🐝", "Атак пчёл", other.get('bee_attacks_count')),
        ])
        embed.add_field(name="🎲 Разное", value=misc_stats, inline=True)
        
        music_stats = "\n".join([
            stat_line("🎵", "Нот сыграно", instruments.get('notes_played')),
            stat_line("🎹", "Бинды нот", instruments.get('note_binds')),
        ])
        embed.add_field(name="🎸 Музыка", value=music_stats, inline=False)
        
        return embed
    
    def get_fishing_embed(self) -> disnake.Embed:
        """Статистика рыбалки"""
        embed = self.get_base_embed()
        embed.title = "🎣 Рыбалка"
        
        fishing = self.data.get("fishing", {})
        
        fish_col1 = "\n".join([
            stat_line("🐟", "Лосось", fishing.get('caught_salmon')),
            stat_line("🐟", "Анчоус", fishing.get('caught_anchovy')),
            stat_line("🐟", "Сом", fishing.get('caught_catfish')),
            stat_line("🐟", "Сельдь", fishing.get('caught_herring')),
            stat_line("🐟", "Сардина", fishing.get('caught_sardine')),
        ])
        embed.add_field(name="🐠 Рыба (1)", value=fish_col1, inline=True)
        
        fish_col2 = "\n".join([
            stat_line("🦈", "Маленькая акула", fishing.get('caught_small_shark')),
            stat_line("🐟", "Форель", fishing.get('caught_small_trout')),
            stat_line("🐟", "Жёлтый окунь", fishing.get('caught_yellow_perch')),
            stat_line("🐟", "Оранжевый ёрш", fishing.get('caught_orange_roughy')),
        ])
        embed.add_field(name="🐠 Рыба (2)", value=fish_col2, inline=True)
        
        return embed
    
    def get_current_embed(self) -> disnake.Embed:
        """Получить текущий embed"""
        embeds = {
            "overview": self.get_overview_embed,
            "kills": self.get_kills_embed,
            "combat": self.get_combat_embed,
            "deaths": self.get_deaths_embed,
            "gathered": self.get_gathered_embed,
            "building": self.get_building_embed,
            "exposure": self.get_exposure_embed,
            "fishing": self.get_fishing_embed,
            "other": self.get_other_embed,
        }
        return embeds.get(self.current_page, self.get_overview_embed)()
    
    async def switch_page(self, inter: disnake.MessageInteraction, page: str):
        """Переключить страницу"""
        self.current_page = page
        self.update_buttons()
        await inter.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @disnake.ui.button(label="Обзор", style=disnake.ButtonStyle.secondary, emoji="📊", row=0)
    async def overview_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.switch_page(inter, "overview")
    
    @disnake.ui.button(label="Убийства", style=disnake.ButtonStyle.secondary, emoji="💀", row=0)
    async def kills_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.switch_page(inter, "kills")
    
    @disnake.ui.button(label="Бой", style=disnake.ButtonStyle.secondary, emoji="🔫", row=0)
    async def combat_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.switch_page(inter, "combat")
    
    @disnake.ui.button(label="Смерти", style=disnake.ButtonStyle.secondary, emoji="☠️", row=1)
    async def deaths_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.switch_page(inter, "deaths")
    
    @disnake.ui.button(label="Ресурсы", style=disnake.ButtonStyle.secondary, emoji="⛏️", row=1)
    async def gathered_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.switch_page(inter, "gathered")
    
    @disnake.ui.button(label="Стройка", style=disnake.ButtonStyle.secondary, emoji="🏗️", row=1)
    async def building_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.switch_page(inter, "building")
    
    @disnake.ui.button(label="Среда", style=disnake.ButtonStyle.secondary, emoji="🌡️", row=2)
    async def exposure_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.switch_page(inter, "exposure")
    
    @disnake.ui.button(label="Рыбалка", style=disnake.ButtonStyle.secondary, emoji="🎣", row=2)
    async def fishing_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.switch_page(inter, "fishing")
    
    @disnake.ui.button(label="Другое", style=disnake.ButtonStyle.secondary, emoji="📋", row=2)
    async def other_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.switch_page(inter, "other")


class RustStats(commands.Cog):
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = "https://ruststats.io/api/rpc/get_profile"
    
    def has_stats_data(self, data: dict) -> bool:
        if not data:
            return False
        
        overview = data.get("overview", {})
        pvp = data.get("pvp_stats", {})
        
        time_played = overview.get("time_played")
        kills = pvp.get("kills")
        
        if time_played or kills:
            return True
        
        return False
    
    @commands.slash_command(name="check", description="Команды для проверки статистики")
    async def check(self, inter: disnake.ApplicationCommandInteraction):
        pass
    
    @check.sub_command(name="account", description="Проверить статистику игрока в Rust")
    async def account(
        self,
        inter: disnake.ApplicationCommandInteraction,
        steam_id: str = commands.Param(
            description="Steam ID, URL профиля или имя пользователя",
            name="steam"
        )
    ):
        await inter.response.defer()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json={"id": steam_id},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status == 404:
                        embed = disnake.Embed(
                            title="❌ Профиль не найден",
                            description="Игрок с указанным Steam ID/URL не найден.\n\n"
                                       "**Убедитесь, что:**\n"
                                       "• Steam ID или URL введены правильно\n"
                                       "• Игрок играл в Rust",
                            color=0xFF0000
                        )
                        await inter.followup.send(embed=embed)
                        return
                    
                    if response.status != 200:
                        embed = disnake.Embed(
                            title="❌ Ошибка API",
                            description=f"Не удалось получить данные. Код ошибки: {response.status}",
                            color=0xFF0000
                        )
                        await inter.followup.send(embed=embed)
                        return
                    
                    data = await response.json()
            
            if not data:
                embed = disnake.Embed(
                    title="❌ Данные не найдены",
                    description="Не удалось получить статистику для этого профиля.",
                    color=0xFF0000
                )
                await inter.followup.send(embed=embed)
                return
            
            if data.get("is_private", False) and not self.has_stats_data(data):
                embed = disnake.Embed(
                    title="🔒 Приватный профиль",
                    description="Этот Steam профиль является приватным и данные отсутствуют в базе.\n\n"
                               "Игроку необходимо:\n"
                               "• Открыть профиль Steam\n"
                               "• Или посетить [ruststats.io](https://ruststats.io) для индексации",
                    color=0xFFA500
                )
                embed.set_thumbnail(url=data.get("avatar_full_url", ""))
                embed.add_field(
                    name="Игрок",
                    value=data.get("personaname", "Unknown"),
                    inline=True
                )
                embed.add_field(
                    name="SteamID",
                    value=data.get("steamid", "N/A"),
                    inline=True
                )
                await inter.followup.send(embed=embed)
                return
            
            view = StatsView(data, inter.author.id)
            embed = view.get_overview_embed()
            
            await inter.followup.send(embed=embed, view=view)
            
        except aiohttp.ClientError as e:
            embed = disnake.Embed(
                title="❌ Ошибка соединения",
                description=f"Не удалось подключиться к API: {str(e)}",
                color=0xFF0000
            )
            await inter.followup.send(embed=embed)
        
        except Exception as e:
            embed = disnake.Embed(
                title="❌ Произошла ошибка",
                description=f"```{str(e)}```",
                color=0xFF0000
            )
            await inter.followup.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(RustStats(bot))
