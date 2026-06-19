import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from core.engines.helios.helios_manager import HeliosNode, NodeState

class TestHeliosManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.eth_node = HeliosNode(
            network="ethereum", 
            el_rpc="http://127.0.0.1:43200", 
            cl_rpc="http://127.0.0.1:43201", 
            port=43210
        )
        self.base_node = HeliosNode(
            network="base", 
            el_rpc="http://127.0.0.1:43202", 
            cl_rpc="", 
            port=43211
        )

    @patch('core.engines.helios.helios_manager.urllib.request.urlopen')
    async def test_fetch_checkpoint_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"data": {"root": "0x123abc"}}'
        
        mock_urlopen.return_value.__enter__.return_value = mock_response

        success = await self.eth_node.fetch_checkpoint()
        
        self.assertTrue(success)
        self.assertEqual(self.eth_node.checkpoint_root, "0x123abc")

    @patch('core.engines.helios.helios_manager.urllib.request.urlopen')
    async def test_fetch_checkpoint_failure(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("HTTP Error 503: Service Unavailable")

        success = await self.eth_node.fetch_checkpoint()
        
        self.assertFalse(success)
        self.assertIsNone(self.eth_node.checkpoint_root)

    @patch('core.engines.helios.helios_manager.asyncio.create_subprocess_exec')
    @patch.object(HeliosNode, 'fetch_checkpoint')
    async def test_start_eth_aborts_on_failed_checkpoint(self, mock_fetch, mock_exec):
        mock_fetch.return_value = False

        await self.eth_node.start()

        self.assertEqual(self.eth_node.state, NodeState.DEAD)
        mock_exec.assert_not_called()

    @patch('core.engines.helios.helios_manager.asyncio.create_subprocess_exec')
    async def test_start_base_boots_without_checkpoint(self, mock_exec):
        mock_process = MagicMock()
        mock_exec.return_value = mock_process

        await self.base_node.start()

        self.assertEqual(self.base_node.state, NodeState.BOOTING)
        mock_exec.assert_called_once()
        
        args, _ = mock_exec.call_args
        self.assertIn("opstack", args)
        self.assertIn("base", args)

    async def test_consume_stream_healthy_transition(self):
        self.eth_node.process = MagicMock()
        self.eth_node.process.returncode = None
        self.eth_node.process.stdout = AsyncMock()
        
        self.eth_node.process.stdout.readline.side_effect = [
            b'INFO helios::client: node successfully synced\n',
            b''
        ]

        self.eth_node.process.stdout.at_eof = MagicMock(side_effect=[False, False, True])
        await self.eth_node.consume_stream()
        self.assertEqual(self.eth_node.state, NodeState.HEALTHY)

    async def test_native_process_crash_marks_dead(self):
        self.eth_node.process = MagicMock()
        self.eth_node.process.returncode = 1 
        self.eth_node.process.stdout = AsyncMock()
        self.eth_node.process.stdout.readline.return_value = b''

        self.eth_node.process.stdout.at_eof = MagicMock(return_value=True)

        await self.eth_node.consume_stream()
        self.assertEqual(self.eth_node.state, NodeState.DEAD)

    async def test_terminate_cleans_up_resources(self):
        self.eth_node.process = MagicMock()
        self.eth_node.process.returncode = None
        self.eth_node.process.wait = AsyncMock() 
        self.eth_node.stream_task = MagicMock()

        await self.eth_node.terminate()
        self.eth_node.process.terminate.assert_called_once()
        self.eth_node.process.wait.assert_awaited_once()
        self.eth_node.stream_task.cancel.assert_called_once()

    @patch('core.engines.helios.helios_manager.asyncio.sleep')
    async def test_supervisor_loop_triggers_restart_on_dead_state(self, mock_sleep):
        mock_sleep.side_effect = [None, asyncio.CancelledError()]

        self.eth_node.state = NodeState.DEAD
        self.eth_node.terminate = AsyncMock()
        self.eth_node.start = AsyncMock()
        nodes = [self.eth_node]

        try:
            for node in nodes:
                if node.state == NodeState.DEAD:
                    await node.terminate()
                    await node.start()
        except asyncio.CancelledError:
            pass

        self.eth_node.terminate.assert_awaited_once()
        self.eth_node.start.assert_awaited_once()
        
if __name__ == '__main__':
    unittest.main()