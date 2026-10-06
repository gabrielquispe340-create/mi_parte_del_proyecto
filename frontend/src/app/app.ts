import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AyudaFlotanteComponent } from './shared/components/ayuda-flotante/ayuda-flotante.component';
import { ToastComponent } from './shared/components/toast/toast.component';

@Component({
  imports: [RouterOutlet, ToastComponent, AyudaFlotanteComponent],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  protected readonly title = signal('EGRESA');
}
