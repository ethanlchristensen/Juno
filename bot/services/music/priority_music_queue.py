import asyncio


class PriorityMusicQueue(asyncio.Queue):
    """Queue with support for adding items to the front"""

    def put_front_nowait(self, item):
        """Put an item at the front of the queue without blocking."""
        if self._is_shutdown:
            raise asyncio.QueueShutDown
        if self.full():
            raise asyncio.QueueFull
        self._queue.appendleft(item)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)

    async def put_front(self, item):
        """Put an item at the front of the queue."""
        while self.full():
            if self._is_shutdown:
                raise asyncio.QueueShutDown
            putter = self._get_loop().create_future()
            self._putters.append(putter)
            try:
                await putter
            except:
                putter.cancel()
                try:
                    self._putters.remove(putter)
                except ValueError:
                    pass
                if not self.full() and not putter.cancelled():
                    self._wakeup_next(self._putters)
                raise
        return self.put_front_nowait(item)
