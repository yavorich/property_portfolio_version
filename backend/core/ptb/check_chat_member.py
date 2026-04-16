from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest, Forbidden


async def is_chat_member(bot, tg_channel_id, tg_user_id):
    # если для tg_channel_id вместо числового id указывается username канала,
    #  то нужно добавить @ перед названием канала
    try:
        chat_member = await bot.get_chat_member(
            chat_id=tg_channel_id, user_id=tg_user_id
        )
    except (BadRequest, Forbidden) as e:
        return e.message != "Participant_id_invalid"

    return chat_member.status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    )
