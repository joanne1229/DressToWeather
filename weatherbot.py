import discord
from discord.ext import commands, tasks
import requests
import datetime
from typing import Dict, Optional
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()


class WeatherBot(commands.Bot):
    def __init__(self, command_prefix):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.weather_api_key = os.getenv('WEATHER_API_KEY')
        self.user_preferences = {}  # Format: {user_id: {"location": city, "time": "HH:MM" , "channel_id": channel_id}}}
        self.scheduled_tasks = {}

        
    async def setup_hook(self):
        await self.schedule_all_tasks()

    def get_weather(self, city: str) -> Optional[Dict]:
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.weather_api_key}&units=metric"
            response = requests.get(url)
            data = response.json()
            if response.status_code == 200:
                return data
            return None
        except Exception as e:
            print(f"Error fetching weather: {e}")
            return None
        
    def is_valid_time_format(self, time_str: str) -> bool:
        try:
            datetime.datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False
        
    async def schedule_weather_task(self, user_id: int, time_str: str):
        # Cancel existing task if it exists
        if user_id in self.scheduled_tasks:
            self.scheduled_tasks[user_id].cancel()

        # Calculate time until first run
        now = datetime.datetime.now()
        target_time = datetime.datetime.strptime(time_str, "%H:%M").time()
        target_datetime = datetime.datetime.combine(now.date(), target_time)
        
        # If target time is already passed today, schedule for tomorrow
        if target_datetime <= now:
            target_datetime += datetime.timedelta(days=1)
        
        delay = (target_datetime - now).total_seconds()

        # Create new task
        async def scheduled_task():
            await asyncio.sleep(delay)
            while True:
                if user_id in self.user_preferences:
                    weather_data = self.get_weather(self.user_preferences[user_id]["location"])
                    if weather_data:
                        user = await self.fetch_user(user_id)
                        channel = self.get_channel(self.user_preferences[user_id]["channel_id"])
                        if channel:
                            await self.send_weather_report(user, weather_data, channel)
                await asyncio.sleep(86400)  # Wait 24 hours before next update

        task = asyncio.create_task(scheduled_task())
        self.scheduled_tasks[user_id] = task

    async def schedule_all_tasks(self):
        # Schedule tasks for all existing users
        for user_id, prefs in self.user_preferences.items():
            await self.schedule_weather_task(user_id, prefs["time"])
    
    def get_outfit_suggestion(self, temp: float, weather_condition: str, wind_speed: float) -> str:
        def get_fem_style(temp: float) -> str:
            if temp >= 90:
                return "Lightweight sundresses, breezy tank tops, loose shorts, hair up in a messy bun or braids for coolness. Consider moisture-wicking fabrics."
            elif temp >= 80:
                return "Flowy midi dresses, cropped tops with high-waisted shorts, light skirts with breathable tops. Consider a light kimono for sun protection."
            elif temp >= 70:
                return "A-line dresses with short sleeves, culottes with blouses, cotton jumpsuits. Add a light cardigan for evening."
            elif temp >= 60:
                return "Midi skirts with light sweaters, shirt dresses with tights, cropped trousers with fitted tops. Layer with a denim jacket or blazer."
            elif temp >= 50:
                return "Sweater dresses with boots, layered tops with ponte pants, long skirts with turtlenecks. Add a trench coat or light wool coat."
            elif temp >= 40:
                return "Wool dresses with thermal tights, chunky sweaters with lined pants, knee-high boots. Layer with a warm peacoat."
            elif temp >= 30:
                return "Insulated leggings under dresses, thermal base layers, chunky knit sweaters, waterproof boots. Add a down coat and warm accessories."
            else:
                return "Heavy thermal layers under warm dresses or pants, insulated boots, maximum layering with wool and down materials."

        def get_masc_style(temp: float) -> str:
            if temp >= 90:
                return "Loose cotton shorts, breathable short-sleeve shirts, lightweight chino shorts. Consider moisture-wicking athletic wear."
            elif temp >= 80:
                return "Bermuda shorts, polo shirts, light chinos with rolled ankles, breathable button-downs with sleeves rolled."
            elif temp >= 70:
                return "Chino shorts or light pants, short-sleeve henley shirts, light cotton button-downs. Add a light pullover for evening."
            elif temp >= 60:
                return "Chinos or jeans with long-sleeve tees, casual button-downs, light sweaters. Layer with a light jacket."
            elif temp >= 50:
                return "Dark jeans or wool pants, flannel shirts, medium-weight sweaters. Add a quilted jacket or heavy blazer."
            elif temp >= 40:
                return "Heavy jeans or wool trousers, thick sweaters, thermal undershirts. Layer with a wool coat."
            elif temp >= 30:
                return "Insulated pants, heavy sweaters with base layers, winter boots. Add a heavy down jacket and warm accessories."
            else:
                return "Maximum layering with thermal base layer, insulated pants, heavy sweater, and serious winter coat."

        fem_outfit = get_fem_style(temp)
        masc_outfit = get_masc_style(temp)
    
        weather_addition = ""
        if weather_condition.lower().find('rain') != -1:
            if wind_speed > 20:
                weather_addition = "\n      ⛈️ Due to wind and rain: Add a waterproof raincoat, avoid umbrellas. Consider waterproof boots and rain pants."
            else:
                weather_addition = "\n      🌧️ For rain: Bring an umbrella, consider water-resistant shoes."
        elif weather_condition.lower().find('snow') != -1:
            weather_addition = "\n      ❄️ For snow: Add waterproof boots, warm socks, and snow-appropriate outerwear."
        elif wind_speed > 20:
            weather_addition = "\n      💨 Due to high winds: Add wind-resistant layers, secure loose items."

        return f"\n      👗 Feminine style: {fem_outfit}\n      👔 Masculine style: {masc_outfit}{weather_addition}"
    
        
    # @tasks.loop(hours=24)
    # async def check_weather(self):
    #     for user_id, location in self.user_locations.items():
    #         weather_data = self.get_weather(location)
    #         if weather_data:
    #             user = await self.fetch_user(user_id)
    #             await self.send_weather_report(user, weather_data)

    async def send_weather_report(self, user, weather_data: Dict, channel=None):
        temp = (weather_data['main']['temp'] * 9/5) + 32
        feels_like = (weather_data['main']['feels_like'] * 9/5) + 32
        wind_speed = weather_data['wind']['speed'] * 2.237  # Convert m/s to mph
        condition = weather_data['weather'][0]['description']
        outfit = self.get_outfit_suggestion(temp, condition, wind_speed)
        wind_description = "Calm"
        if wind_speed < 5:
            wind_description = "Calm"
        elif wind_speed < 12:
            wind_description = "Light breeze"
        elif wind_speed < 20:
            wind_description = "Moderate breeze"
        elif wind_speed < 30:
            wind_description = "Strong breeze"
        else:
            wind_description = "Very windy"
        
        message = (
            f"Weather report for {user.mention}:\n"
            f"🌡️ Temperature: {temp}°F\n"
            f"🌪️ Feels like: {feels_like:.1f}°F\n"
            f"💨 Wind: {wind_description} ({wind_speed:.1f} mph)\n"
            f"🌤️ Condition: {condition}\n"
            f"👖 Suggested outfit: {outfit}"
        )
        
        if channel:
            await channel.send(message)
        else:
            await user.send(message)  # Fallback to DM if no channel provided


bot = WeatherBot(command_prefix='!')

try:
    bot = WeatherBot(command_prefix='!')
except Exception as e:
    print(f"Failed to initialize bot: {e}")
    exit(1)

@bot.command(name='weather')
async def weather(ctx, *, city: str):
    """Get current weather and outfit suggestion for a city"""
    weather_data = bot.get_weather(city)
    if weather_data:
        await bot.send_weather_report(ctx.author, weather_data, ctx.channel)
    else:
        await ctx.send("Sorry, couldn't find weather data for that location.")

@bot.command(name='setlocation')
async def set_location(ctx, city: str, time: str = None):
    """Set your default location and preferred time (in EST) for daily updates"""
    if not time:
        await ctx.send("Please provide both city and time in 24-hour format (EST). Example: !setlocation 'New York' 08:00")
        return

    if not bot.is_valid_time_format(time):
        await ctx.send("Invalid time format. Please use 24-hour format (HH:MM). Example: 08:00 for 8 AM, 13:30 for 1:30 PM")
        return

    weather_data = bot.get_weather(city)
    if weather_data:
        bot.user_preferences[ctx.author.id] = {
            "location": city,
            "time": time,
            "channel_id": ctx.channel.id
        }
        # Schedule the new task
        await bot.schedule_weather_task(ctx.author.id, time)
        await ctx.send(f"Location set to {city}. You'll receive daily weather updates at {time} EST!")
    else:
        await ctx.send("Invalid location. Please try again.")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

try:
    bot.run(os.getenv('DISCORD_TOKEN'))
except discord.LoginFailure:
    print("Failed to login. Please check your token.")
except Exception as e:
    print(f"An error occurred: {e}")