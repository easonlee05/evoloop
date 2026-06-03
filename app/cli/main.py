"""Evoloop 3.0 CLI Entry Point."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from app.cli.commands import compile_cmd, package_cmd, acceptance_cmd, review_cmd


def main(args: Optional[List[str]] = None) -> None:
    """Parse command line arguments and execute the corresponding command."""
    parser = argparse.ArgumentParser(
        description="Evoloop 3.0 CLI Adapter - Control Digital PM Capability from Terminal"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # compile command parser
    compile_parser = subparsers.add_parser("compile", help="Compile intent into specification")
    compile_parser.add_argument(
        "-i", "--intent", 
        type=str, 
        required=True, 
        help="Business intent or requirement statement"
    )
    compile_parser.add_argument(
        "-m", "--materials", 
        type=str, 
        nargs="*", 
        default=[], 
        help="Path(s) to referenced materials or context files"
    )
    compile_parser.add_argument(
        "--output-dir", 
        type=str, 
        default=".", 
        help="Output directory to write machine_spec.yaml and human_brief.md"
    )
    compile_parser.add_argument(
        "--fake", 
        action="store_true", 
        help="Run in mock/fake mode without calling real LLM APIs"
    )

    # package command parser
    package_parser = subparsers.add_parser("package", help="Generate AI agent package from spec")
    package_parser.add_argument(
        "-s", "--spec", 
        type=str, 
        default="./machine_spec.yaml", 
        help="Path to machine_spec.yaml"
    )
    package_parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="./agent_package.md", 
        help="Output path for agent_package.md"
    )
    package_parser.add_argument(
        "--fake", 
        action="store_true", 
        help="Run in mock/fake mode without calling real LLM APIs"
    )

    # acceptance command parser
    acceptance_parser = subparsers.add_parser("acceptance", help="Generate acceptance protocol from spec")
    acceptance_parser.add_argument(
        "-s", "--spec", 
        type=str, 
        default="./machine_spec.yaml", 
        help="Path to machine_spec.yaml"
    )
    acceptance_parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="./acceptance.md", 
        help="Output path for acceptance.md"
    )
    acceptance_parser.add_argument(
        "--fake", 
        action="store_true", 
        help="Run in mock/fake mode without calling real LLM APIs"
    )

    # review command parser
    review_parser = subparsers.add_parser("review", help="Review worker deliverables against acceptance criteria")
    review_parser.add_argument(
        "-s", "--spec", 
        type=str, 
        default="./machine_spec.yaml", 
        help="Path to machine_spec.yaml"
    )
    review_parser.add_argument(
        "-a", "--acceptance", 
        type=str, 
        default="./acceptance.md", 
        help="Path to acceptance.md protocol"
    )
    review_parser.add_argument(
        "-d", "--delivery", 
        type=str, 
        required=True, 
        help="AI worker's delivery text content or file path containing the outputs"
    )
    review_parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="./review_result.md", 
        help="Output path for review_result.md"
    )
    review_parser.add_argument(
        "--fake", 
        action="store_true", 
        help="Run in mock/fake mode without calling real LLM APIs"
    )

    parsed_args = parser.parse_args(args)

    if parsed_args.command == "compile":
        compile_cmd(
            intent=parsed_args.intent,
            materials=parsed_args.materials,
            output_dir=parsed_args.output_dir,
            fake=parsed_args.fake
        )
    elif parsed_args.command == "package":
        package_cmd(
            spec_path=parsed_args.spec,
            output_path=parsed_args.output,
            fake=parsed_args.fake
        )
    elif parsed_args.command == "acceptance":
        acceptance_cmd(
            spec_path=parsed_args.spec,
            output_path=parsed_args.output,
            fake=parsed_args.fake
        )
    elif parsed_args.command == "review":
        review_cmd(
            spec_path=parsed_args.spec,
            acceptance_path=parsed_args.acceptance,
            delivery_text_or_path=parsed_args.delivery,
            output_path=parsed_args.output,
            fake=parsed_args.fake
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
