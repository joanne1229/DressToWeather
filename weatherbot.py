import discord
from discord.ext import commands, tasks
import requests
import datetime
from typing import Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()


class WeatherBot(commands.Bot):
    def __init__(self, command_prefix):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.weather_api_key = os.getenv('WEATHER_API_KEY')
        self.user_locations = {}
        
    async def setup_hook(self):
        self.check_weather.start()

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
    
    # Add weather-specific modifications
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

    @tasks.loop(hours=24)
    async def check_weather(self):
        for user_id, location in self.user_locations.items():
            weather_data = self.get_weather(location)
            if weather_data:
                user = await self.fetch_user(user_id)
                await self.send_weather_report(user, weather_data)

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
async def set_location(ctx, *, city: str):
    """Set your default location for daily updates"""
    weather_data = bot.get_weather(city)
    if weather_data:
        bot.user_locations[ctx.author.id] = city
        await ctx.send(f"Location set to {city}. You'll receive daily weather updates!")
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