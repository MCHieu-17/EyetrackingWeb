# k6 summary

scenario: outline

- vus: min=5.000, max=5.000
- http_req_connecting: max=0.092, p(90)=0.000, p(95)=0.000, p(99)=0.089, avg=0.002, min=0.000, med=0.000
- iterations: count=240.000, rate=23.676
- http_req_failed: rate=0.000
- http_req_duration: max=47.996, p(90)=12.199, p(95)=12.982, p(99)=32.717, avg=8.768, min=1.881, med=7.953
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_receiving: avg=0.156, min=0.016, med=0.125, max=1.030, p(90)=0.307, p(95)=0.370, p(99)=0.838
- http_req_blocked: med=0.011, max=0.133, p(90)=0.014, p(95)=0.015, p(99)=0.121, avg=0.013, min=0.003
- http_req_sending: max=0.138, p(90)=0.049, p(95)=0.057, p(99)=0.068, avg=0.040, min=0.008, med=0.040
- http_req_duration{expected_response:true}: avg=8.768, min=1.881, med=7.953, max=47.996, p(90)=12.199, p(95)=12.982, p(99)=32.717
- http_req_waiting: min=1.827, med=7.763, max=47.908, p(90)=11.881, p(95)=12.600, p(99)=32.564, avg=8.572
