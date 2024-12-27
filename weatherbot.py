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
        
    def get_forecast(self, city: str) -> Optional[Dict]:
        try:
            url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={self.weather_api_key}&units=metric"
            response = requests.get(url)
            data = response.json()
            if response.status_code == 200:
                return data
            return None
        except Exception as e:
            print(f"Error fetching forecast: {e}")
            return None

    def get_precipitation_warning(self, city: str) -> str:
        forecast = self.get_forecast(city)
        if not forecast:
            return ""
    
        current_time = datetime.datetime.now()
        end_time = current_time + datetime.timedelta(hours=12)
    
        precipitation_times = []
        for period in forecast['list']:
            period_time = datetime.datetime.fromtimestamp(period['dt'])
        
            if period_time > end_time:
                break
            
            weather = period['weather'][0]['main'].lower()
            if 'rain' in weather or 'snow' in weather:
                formatted_time = period_time.strftime('%I:%M %p')
                hours_from_now = round((period_time - current_time).total_seconds() / 3600)
                time_detail = f"{formatted_time} ({hours_from_now}h from now)"
                precipitation_times.append((time_detail, weather))
    
        if precipitation_times:
            time, weather = precipitation_times[0]  # Get only first precipitation event
            emoji = '🌧️' if 'rain' in weather else '❄️'
            return f"\n⚠️ Weather Alert: {emoji} {weather.title()} expected at {time}"
        return ""
        
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
        def get_outfits(temp: float) -> dict:
            if temp >= 90:
                return {
                    "tops": "Lightweight and breathable: tank tops, sleeveless shirts, loose-fitting tees",
                    "bottoms": "Shorts, lightweight skirts, breathable loose pants",
                    "shoes": "Sandals, breathable sneakers, open-toed shoes",
                    "accessories": "Wide-brimmed hat, sunglasses, cooling neck wrap",
                    "layers": "Consider a light cotton shawl or kimono for sun protection"
                }
            elif temp >= 80:
                return {
                "tops": "Breathable short-sleeves, lightweight button-ups, breezy blouses",
                "bottoms": "Shorts, skirts, lightweight pants, capris",
                "shoes": "Comfortable sandals, breathable sneakers, lightweight shoes",
                "accessories": "Sunglasses, hat, lightweight scarf",
                "layers": "Light cardigan or shawl for indoor AC"
            }
            elif temp >= 70:
                return {
                "tops": "T-shirts, short-sleeve button-ups, light sweaters",
                "bottoms": "Light pants, knee-length skirts, cropped pants",
                "shoes": "Sneakers, loafers, light boots",
                "accessories": "Light scarf, sunglasses",
                "layers": "Light jacket or cardigan for evening"
            }
            elif temp >= 60:
                return {
                "tops": "Long-sleeve shirts, light sweaters, button-ups",
                "bottoms": "Full-length pants, midi skirts, regular jeans",
                "shoes": "Closed-toe shoes, light boots, sneakers",
                "accessories": "Light scarf, beanie",
                "layers": "Light jacket, denim jacket, or blazer"
            }
            elif temp >= 50:
                return {
                "tops": "Sweaters, long-sleeve shirts, turtlenecks",
                "bottoms": "Warm pants, thick leggings, wool skirts",
                "shoes": "Boots, closed-toe shoes, warm socks",
                "accessories": "Scarf, warm hat, gloves",
                "layers": "Medium-weight jacket or coat"
            }
            elif temp >= 40:
                return {
                "tops": "Thick sweaters, thermal shirts, fleece tops",
                "bottoms": "Warm pants, thermal leggings, insulated bottoms",
                "shoes": "Insulated boots, warm socks",
                "accessories": "Warm scarf, beanie, gloves",
                "layers": "Heavy coat, consider thermal underlayers"
            }
            elif temp >= 30:
                return {
                "tops": "Thermal base layer, thick sweaters, fleece",
                "bottoms": "Insulated pants, thermal leggings, warmest options",
                "shoes": "Insulated waterproof boots, wool socks",
                "accessories": "Thick scarf, warm hat, insulated gloves",
                "layers": "Heavy winter coat, thermal underlayers essential"
            }
            else:
                return {
                "tops": "Maximum thermal layers, heaviest sweaters",
                "bottoms": "Insulated pants, thermal base layer",
                "shoes": "Insulated snow boots, multiple layers of socks",
                "accessories": "Warmest hat, scarf, and gloves/mittens",
                "layers": "Heaviest winter coat, multiple thermal layers"
            }

        outfit = get_outfits(temp)
    
        weather_addition = ""
        if weather_condition.lower().find('rain') != -1:
            if wind_speed > 20:
                weather_addition = "\n      ⛈️ Weather protection: Add a sturdy waterproof raincoat and water-resistant pants. Skip the umbrella - it won't survive!"
            else:
                weather_addition = "\n      🌧️ Weather protection: Pack an umbrella and wear water-resistant footwear"
        elif weather_condition.lower().find('snow') != -1:
            weather_addition = "\n      ❄️ Weather protection: Waterproof boots, snow gear, and extra warm socks essential"
        elif wind_speed > 20:
            weather_addition = "\n      💨 Weather protection: Add wind-resistant outer layer, secure loose items and accessories"

        return (
        f"\n      👕 Tops: {outfit['tops']}"
        f"\n      👖 Bottoms: {outfit['bottoms']}"
        f"\n      👟 Shoes: {outfit['shoes']}"
        f"\n      🧣 Accessories: {outfit['accessories']}"
        f"\n      🧥 Layers: {outfit['layers']}"
        f"{weather_addition}"
        )
    
    def get_sunscreen_advice(self, temp: float, condition: str) -> str:
        condition = condition.lower()
        if any(word in condition for word in ['clear', 'sun', 'fair']):
            if temp > 75:
                return "\n      🧴 HIGH UV ALERT: Don't forget SPF 50+! Reapply every 2 hours. Your future self (and dermatologist) will thank you!"
            else:
                return "\n      🧴 Moderate UV levels: SPF 30+ recommended. Yes, even on cooler days - those UV rays are sneaky!"
        elif any(word in condition for word in ['cloud', 'overcast', 'fog']):
            return "\n      🧴 UV Reminder: Clouds only block 20% of UV rays - SPF 30 is still your friend!"
        elif any(word in condition for word in ['rain', 'storm', 'thunder']):
            return "\n      🧴 Low UV today, but if it clears up, don't forget your sunscreen!"
        else:
            return "\n      🧴 Better safe than sorry - pack that sunscreen!"

    def get_wind_description(self, wind_speed: float) -> str:
        if wind_speed < 5:
            return "Calm - Perfect for that freshly styled hair!"
        elif wind_speed < 12:
            return "Light breeze - Your picnic napkins might want to escape"
        elif wind_speed < 20:
            return "Moderate breeze - Hold onto your hat and those loose papers!"
        elif wind_speed < 30:
            return "Strong breeze - Your umbrella wants to be Mary Poppins & those false lashes might try to take flight"
        elif wind_speed < 40:
            return "Very windy - Your wig is plotting its escape & skirts are becoming dangerous"
        else:
            return "Extremely windy - Everything not bolted down is becoming a projectile & your hairdo doesn't stand a chance"

    async def send_weather_report(self, user, weather_data: Dict, channel=None):
        temp = round((weather_data['main']['temp'] * 9/5) + 32)
        feels_like = round((weather_data['main']['feels_like'] * 9/5) + 32)
        wind_speed = round(weather_data['wind']['speed'] * 2.237)  # Convert m/s to mph
        condition = weather_data['weather'][0]['description']
        outfit = self.get_outfit_suggestion(temp, condition, wind_speed)
        sunscreen_advice = self.get_sunscreen_advice(temp, condition)
        wind_description = self.get_wind_description(wind_speed)
        precipitation_warning = self.get_precipitation_warning(weather_data['name'])
        
        message = (
            f"Weather report for {user.mention}:\n"
            f"🌡️ Temperature: {temp:.1f}°F\n"
            f"🌪️ Feels like: {feels_like:.1f}°F\n"
            f"💨 Wind: {wind_description} ({wind_speed:.1f} mph)\n"
            f"🌤️ Condition: {condition}"
            f"{precipitation_warning}\n"
            f"🥼 Suggested outfit: {outfit}"
            f"{sunscreen_advice}"
        )
        
        if channel:
            await channel.send(message)
        else:
            await user.send(message)  # Fallback to DM if no channel provided


bot = WeatherBot(command_prefix='!')

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

