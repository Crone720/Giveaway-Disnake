import disnake, aiosqlite, datetime, asyncio, random
from disnake.ext import commands
from typing import List

async def get_giveaway_info(giveaway_id: int):
    async with aiosqlite.connect('giveaway.db') as db:
        cursor = await db.execute("SELECT channelid, messageid FROM giveaway WHERE id=?", (giveaway_id,))
        result = await cursor.fetchone()
        if result:
            return result
        else:
            return (None, None)


async def pick_winner(giveaway_id: int):
    async with aiosqlite.connect('giveaway.db') as db:
        cursor = await db.execute("SELECT user_id FROM participants WHERE giveaway_id=?", (giveaway_id,))
        participants = await cursor.fetchall()
        if participants:
            winner = random.choice(participants)[0]
            return winner
        else:
            return None

async def pick_new_winner(giveaway_id: int):
    async with aiosqlite.connect('giveaway.db') as db:
        cursor = await db.execute("SELECT user_id FROM participants WHERE giveaway_id=?", (giveaway_id,))
        participants = await cursor.fetchall()
        if participants:
            previous_winner = await pick_winner(giveaway_id)
            participants_without_winner = [participant[0] for participant in participants if participant[0] != previous_winner]
            if participants_without_winner:
                new_winner = random.choice(participants_without_winner)
                return new_winner
            else:
                return None
        else:
            return None

async def fetch_giveaway_entries(giveaway_id: int):
    async with aiosqlite.connect('giveaway.db') as db:
        cursor = await db.execute("SELECT user_id FROM participants WHERE giveaway_id=?", (giveaway_id,))
        entries = await cursor.fetchall()
        return entries
async def get_message(giveaway_id):
    async with aiosqlite.connect('giveaway.db') as db:
        cursor = await db.execute("SELECT messageid FROM giveaway WHERE id=?", (giveaway_id,))
        row = await cursor.fetchone()
        if row:
            return row[0]
        else:
            return None

async def create_tables():
    async with aiosqlite.connect('giveaway.db') as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway (
                id INTEGER PRIMARY KEY,
                channelid INTEGER,
                messageid INTEGER,
                prize TEXT,
                time INT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY,
                giveaway_id INTEGER,
                user_id INTEGER,
                FOREIGN KEY(giveaway_id) REFERENCES giveaway(id)
            )
        """)
        await db.commit()

async def save_giveaway(channel_id, message_id, prize, end_time):
    async with aiosqlite.connect('giveaway.db') as db:
        cursor = await db.execute("""
            INSERT INTO giveaway (channelid, messageid, prize, time)
            VALUES (?, ?, ?, ?)
        """, (channel_id, message_id, prize, int(end_time.timestamp())))
        await db.commit()
        return cursor.lastrowid
    
async def add_participant(user_id, giveaway_id):
    async with aiosqlite.connect('giveaway.db') as db:
        await db.execute("INSERT INTO participants (giveaway_id, user_id) VALUES (?, ?)", (giveaway_id, user_id))
        await db.commit()

async def pick_winners(giveaway_id, winners_count):
    async with aiosqlite.connect('giveaway.db') as db:
        cursor = await db.execute("SELECT user_id FROM participants WHERE giveaway_id=?", (giveaway_id,))
        participants = await cursor.fetchall()
        if participants:
            winners = random.sample(participants, winners_count)
            return [winner[0] for winner in winners]
        else:
            return []

async def check_participation(user_id, giveaway_id):
    async with aiosqlite.connect('giveaway.db') as db:
        cursor = await db.execute("SELECT * FROM participants WHERE giveaway_id=? AND user_id=?", (giveaway_id, user_id))
        row = await cursor.fetchone()
        return row is not None

async def remove_participant(user_id, giveaway_id):
    async with aiosqlite.connect('giveaway.db') as db:
        await db.execute("DELETE FROM participants WHERE giveaway_id=? AND user_id=?", (giveaway_id, user_id))
        await db.commit()

class EntriesPaginator(disnake.ui.View):
    def __init__(self, embeds: List[disnake.Embed]):
        super().__init__(timeout=None)
        self.embeds = embeds
        self.index = 0

        self._update_state()

    def _update_state(self) -> None:
        self.prev_page.disabled = self.index == 0
        self.next_page.disabled = self.index == len(self.embeds) - 1

    @disnake.ui.button(label="<<", style=disnake.ButtonStyle.secondary)
    async def prev_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.index -= 1
        self._update_state()

        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @disnake.ui.button(label=">>", style=disnake.ButtonStyle.secondary)
    async def next_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.index += 1
        self._update_state()

        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

class SecondGiveawayButton(disnake.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @disnake.ui.button(label="Покинуть", style=disnake.ButtonStyle.gray, custom_id="leavegiveaway")
    async def leavegiveaway(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        async with aiosqlite.connect('giveaway.db') as db:
            await db.execute("DELETE FROM participants WHERE giveaway_id=? AND user_id=?", (self.giveaway_id, interaction.author.id))
            await db.commit()
            embed = disnake.Embed(title="Розыгрыш", description="Вы успешно покинули розыгрыш", color=disnake.Color.red())
            await interaction.response.edit_message(embed=embed, view=None)

class MembersGiveAwayButton(disnake.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
    @disnake.ui.button(label="Участники", style=disnake.ButtonStyle.gray, custom_id="membersgiveaway")
    async def membersgiveaway(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        entries = await fetch_giveaway_entries(self.giveaway_id)
        
        if not entries:
            embed = disnake.Embed(description="Никто не участвует.", color=0x2F3136)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embeds = []
            for i in range(0, len(entries), 50):
                entries_mentions = "\n".join([f"{i+1}) <@{entry[0]}>" for i, entry in enumerate(entries[i:i+50])])
                embed = disnake.Embed(title=f"Участники Розыгрыша, всего {len(entries)}", description=entries_mentions, color=0x2F3136)
                embed.set_thumbnail(url=interaction.author.avatar.url if interaction.author.avatar else interaction.author.default_avatar.url)
                embeds.append(embed)
            await interaction.response.send_message(embed=embeds[0], view=EntriesPaginator(embeds), ephemeral=True)
class FirstGiveawayButton(disnake.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @disnake.ui.button(label="🍭", style=disnake.ButtonStyle.gray, custom_id="joingiveaway")
    async def joingiveaway(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        user_id = interaction.user.id
        is_participating = await check_participation(user_id, self.giveaway_id)
        if is_participating:
            embed = disnake.Embed(title="Розыгрыш", description="Вы уже **приняли** участие в этом розыгрыше")
            await interaction.response.send_message(embed=embed, view=SecondGiveawayButton(self.giveaway_id),ephemeral=True)
            return
        await add_participant(user_id, self.giveaway_id)
        embed = disnake.Embed(title="Розыгрыш", description="Вы приняли участие в розыгрыше", color=disnake.Color.green())
        embed.set_thumbnail(url=interaction.author.display_avatar)
        await interaction.send(embed=embed, ephemeral=True)

    @disnake.ui.button(label="Участники", style=disnake.ButtonStyle.gray, custom_id="membersgiveaway")
    async def membersgiveaway(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        entries = await fetch_giveaway_entries(self.giveaway_id)
        
        if not entries:
            embed = disnake.Embed(description="Никто не участвует.", color=0x2F3136)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embeds = []
            for i in range(0, len(entries), 15):
                entries_mentions = "\n".join([f"{i+1}) <@{entry[0]}>" for i, entry in enumerate(entries[i:i+15])])
                embed = disnake.Embed(title=f"Участники Розыгрыша, всего {len(entries)}", description=entries_mentions, color=0x2F3136)
                embed.set_thumbnail(url=interaction.author.avatar.url if interaction.author.avatar else interaction.author.default_avatar.url)
                embeds.append(embed)
            await interaction.response.send_message(embed=embeds[0], view=EntriesPaginator(embeds), ephemeral=True)

class GiveawayCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await create_tables()

    @commands.slash_command(name="g")
    async def gmain(self, interaction):
        ...

    @gmain.sub_command(name="create")
    async def gcreate(self, interaction: disnake.AppCommandInteraction,
                      duration: int = commands.Param(description="Время измеряется в минутах"),
                      winnerscount: int = commands.Param(description="Кол-Во победителей (до 3)"),
                      prize: str = commands.Param(description="Приз")):
        if winnerscount > 3:
            await interaction.send("Победителей не может быть больше 3", ephemeral=True)
            return
        if duration <= 0:
            await interaction.send("Вы не можете ввести отрицательное значение или ноль", ephemeral=True)
            return
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(minutes=duration)
        love_time_R = disnake.utils.format_dt(end_time, style="R")
        love_time_F = disnake.utils.format_dt(end_time, style="F")
        embed = disnake.Embed(title="Розыгрыш", description=f"Начал розыгрыш: {interaction.author.mention}\n"
                                                        f"Розыгрыш закончится через: {love_time_R} \n({love_time_F})\n"
                                                        f"Приз: {prize}\n"
                                                        f"Кол-Во победителей: {winnerscount}")
        message = await interaction.channel.send(embed=embed)

        giveaway_id = await save_giveaway(interaction.channel_id, message.id, prize, end_time)
        await interaction.send(f"Вы Успешно создали розыгрыш\nID Розыгрыша: {giveaway_id} не потеряйте его)", ephemeral=True)
        await message.edit(view=FirstGiveawayButton(giveaway_id))
        await asyncio.sleep(duration * 60)
        winner_ids = await pick_winners(giveaway_id, winnerscount)
        if winner_ids:
            message_id = await get_message(giveaway_id)
            if message_id:
                channel = self.bot.get_channel(interaction.channel_id)
                message = await channel.fetch_message(message_id)
                await message.edit(view=MembersGiveAwayButton(giveaway_id))
                winners_mention = " ".join([f"<@{winner_id}>" for winner_id in winner_ids])
                await message.reply(f"Поздравляем {winners_mention} с выигрышем {prize}!")
            else:
                print("Сообщение розыгрыша не найдено.")
        else:
            await interaction.channel.send("Нет участников, никто не выиграл.")
            await message.edit(view=None)

    @gmain.sub_command(name="reroll")
    async def greroll(self, interaction: disnake.AppCommandInteraction, giveawayid: str = commands.Param(description="Укажите ID розыгрыша")):
        new_winner = await pick_new_winner(giveawayid)
        if not new_winner:
            await interaction.response.send_message("Не удалось выбрать нового победителя для реролла.", ephemeral=True)
            return

        channel_id, message_id = await get_giveaway_info(giveawayid)
        if not channel_id or not message_id:
            await interaction.response.send_message("Информация о розыгрыше не найдена.", ephemeral=True)
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("Канал для розыгрыша не доступен.", ephemeral=True)
            return
        print(channel_id)
        message = await channel.fetch_message(message_id)
        await interaction.send("Вы успешно сделали реролл", ephemeral=True)
        await message.reply(f"Реролл, новый победитель <@{new_winner}>")
        
def setup(bot):
    bot.add_cog(GiveawayCommand(bot))
