import asyncio
import os
import sys

from pymongo import MongoClient
from telethon import events, TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.types import Channel, Message, MessageMediaDocument

import configs

client = TelegramClient(configs.api_tg_session_name, configs.api_id, configs.api_hash)

cluster = MongoClient(configs.MONGO_URL)
# cluster = motor.motor_tornado.MotorClient(MONGO_URL)  # if async running db queries
collchannels = cluster.tgparser.channels
colltexts = cluster.tgparser.texts
channel_list = [i['username'] for i in collchannels.find({})]
client.start()


def monitor(downloaded: int, total: int):
    per = round(downloaded / total * 100)
    sys.stdout.write("\rDownloading...(%s%%)" % per)
    sys.stdout.flush()


@client.on(events.NewMessage(channel_list) if channel_list else events.NewMessage())
async def main(event: events.NewMessage.Event):
    msg: Message = event.message

    if isinstance(await client.get_entity(msg.peer_id), Channel):
        start_text = "Starting download: https://t.me/c/{}/{}".format(
            str(msg.peer_id.channel_id), str(msg.id))
        await client.send_message("me", start_text)
    else:
        await event.reply("Starting...\n")

    if msg.media and isinstance(msg.media, MessageMediaDocument):
        if msg.media.document.size > 90427532:
            x = await client.download_media(msg, file="media/",
                                            progress_callback=monitor)
            if isinstance(await client.get_entity(msg.peer_id), Channel):
                content_link = "Downloaded: https://t.me/c/{}/{}".format(
                    str(msg.peer_id.channel_id), str(msg.id))
                x += "\n" + content_link
                await client.send_message("me", x)
            else:
                await event.reply("Downloaded...\n"+x)
                await event.reply(x)


@client.on(events.NewMessage(outgoing=True, pattern='!add_text'))
async def add_text(event):
    adding_text = event.message.message.replace("!add_text", "")
    if adding_text == "":
        m = await event.reply("Error: Please add non-empty text")
    else:
        colltexts.insert_one({"id": event.id,
                              "message": adding_text})
        m = await event.reply('!success')
    await asyncio.sleep(5)
    await client.delete_messages(event.chat_id, [event.id, m.id])


@client.on(events.NewMessage(outgoing=True, pattern='!show_texts'))
async def show_texts(event):
    text_list = ""
    msg_db_list = [f'{i["id"]}: {i["message"]}\n' for i in colltexts.find({})]
    for text in msg_db_list:
        text_list += text
    await event.respond(text_list, link_preview=False)


@client.on(events.NewMessage(outgoing=True, pattern='!del_text'))
async def del_text(event):
    delete_id: str = event.message.message.replace("!del_text ", "")
    if delete_id == "":
        m = await event.reply("Error: Please add non-empty text id")
    elif delete_id.isdigit():
        colltexts.delete_one({"id": int(delete_id)})
        m = await event.reply('!success')
    else:
        m = await event.reply("Error: Please send me normal id number")
    await asyncio.sleep(5)
    await client.delete_messages(event.chat_id, [event.id, m.id])


@client.on(events.NewMessage(outgoing=True, pattern='!add_channel'))
async def add_channel(event):
    channel_link: str = event.message.message.replace("!add_channel ", "").replace("@", "")
    if isinstance(await client.get_entity(channel_link), Channel):
        try:
            await client(JoinChannelRequest(channel_link))
            collchannels.insert_one({"username": channel_link})
            m = await event.reply('!success')
            await asyncio.sleep(1)
            await client.delete_messages(event.chat_id, [event.id, m.id])
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            collchannels.delete_one({"username": channel_link})
            await event.respond(f"Error: {e}")
    else:
        collchannels.insert_one({"username": channel_link})


@client.on(events.NewMessage(outgoing=True, pattern='!show_channels'))
async def show_channels(event):
    ch_text = "Channels:\n"
    ch_list = [i['username'] for i in collchannels.find({})]
    for i in ch_list:
        ch_text += i + "\n"
    return await event.respond(ch_text)


@client.on(events.NewMessage(outgoing=True, pattern='!del_channel'))
async def delete_channel(event):
    channel_link: str = event.message.message.replace("!del_channel ", "").replace("@", "")
    collchannels.delete_one({'username': channel_link})
    await client(LeaveChannelRequest(channel_link))
    os.execv(sys.executable, [sys.executable] + sys.argv)


@client.on(events.NewMessage(outgoing=True, pattern='!help'))
async def help_message(event):
    return await event.respond('! add_text **This text** — adding new text\n'
                               '! show_texts — showing texts\n'
                               '! del_text **message_id** — deleting text by id\n'
                               '! add_channel **channel_link** — adding new channel\n'
                               '! show_channels — showing channels\n'
                               '! del_channel **channel_username** — deleting channel from list')


client.run_until_disconnected()
