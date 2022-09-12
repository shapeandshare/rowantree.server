import json
import logging
import random
from abc import abstractmethod
from typing import Optional

from pydantic import BaseModel

from rowantree.contracts import Action, ActionQueue, StoreType, UserEvent, UserEventOtherType, UserStore
from rowantree.service.sdk import RowanTreeService

from ..common.abstract_loremaster import AbstractLoremaster


class AbstractPersonality(BaseModel):
    """
    GlobalPersonality (Default)
    Generates game world content.

    Attributes
    ----------
    rowantree_service: RowanTreeService
        The Rowan Tree Service Interface.
    loremaster: AbstractLoremaster
        An instance of a story teller for encounter generation.
    """

    rowantree_service: RowanTreeService
    loremaster_service: AbstractLoremaster

    class Config:
        """Pydantic Default Config Over-Rides"""

        arbitrary_types_allowed = True

    ##############
    ## Event Queueing
    ##############

    # TODO: Review the complexity of this
    # pylint: disable=too-many-branches
    def _process_user_event(self, event: Optional[UserEvent], target_user: str) -> None:
        """
        Processes the provided user event (applies the state change of the event)

        Parameters
        ----------
        event: Optional[dict]
            The optional event to process.

        target_user: str
            The target user guid.
        """

        if event is None:
            return

        action_queue: ActionQueue = ActionQueue(queue=[])
        user_stores: dict[StoreType, UserStore] = self.rowantree_service.user_stores_get(user_guid=target_user)

        # process rewards
        for reward in event.reward.keys():
            amount: int = random.randint(1, event.reward[reward])  # Determine an amount up to the max specified.

            if reward == UserEventOtherType.POPULATION:
                action_queue.queue.append(Action(name="deltaUserPopulationByGUID", arguments=[target_user, amount]))
                event.reward[reward] = amount  # Update to the actual amount
            else:
                if reward in user_stores:
                    store_amt: int = user_stores[reward].amount
                    if store_amt < amount:
                        amount = store_amt

                    action_queue.queue.append(
                        Action(name="deltaUserStoreByStoreNameByGUID", arguments=[target_user, reward, amount])
                    )
                    event.reward[reward] = amount

        # process curses
        for curse in event.curse.keys():
            if curse == UserEventOtherType.POPULATION:
                pop_amount: int = random.randint(1, event.curse[curse])
                user_population: int = self.rowantree_service.user_population_get(user_guid=target_user)
                if user_population < pop_amount:
                    pop_amount: int = user_population

                action_queue.queue.append(
                    Action(name="deltaUserPopulationByGUID", arguments=[target_user, (pop_amount * -1)])
                )
                event.curse[curse] = pop_amount
            else:
                amount: int = random.randint(1, event.curse[curse])
                if curse in user_stores:
                    store_amt = user_stores[curse].amount
                    if store_amt < amount:
                        amount = store_amt

                action_queue.queue.append(
                    Action(name="deltaUserStoreByStoreNameByGUID", arguments=[target_user, curse, (amount * -1)])
                )
                event.curse[curse] = amount

        # Send them the whole event object.
        action_queue.queue.append(Action(name="sendUserNotificationByGUID", arguments=[target_user, json.dumps(event)]))

        logging.debug(action_queue.json(by_alias=True))
        self.rowantree_service.action_queue_process(queue=action_queue)

    @abstractmethod
    def contemplate(self):
        """ """