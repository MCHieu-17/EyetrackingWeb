# k6 summary

scenario: samples

- http_req_receiving: p(90)=0.330, p(95)=0.435, p(99)=1.075, avg=0.158, min=0.024, med=0.093, max=1.522
- http_req_failed: rate=0.000
- iterations: rate=22.601, count=231.000
- http_req_duration: p(99)=46.688, avg=16.740, min=5.428, med=13.744, max=51.544, p(90)=27.410, p(95)=30.459
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_connecting: med=0.000, max=0.092, p(90)=0.000, p(95)=0.000, p(99)=0.089, avg=0.002, min=0.000
- http_req_blocked: min=0.002, med=0.010, max=0.126, p(90)=0.014, p(95)=0.016, p(99)=0.121, avg=0.013
- http_req_duration{expected_response:true}: p(90)=27.410, p(95)=30.459, p(99)=46.688, avg=16.740, min=5.428, med=13.744, max=51.544
- vus: max=5.000, min=5.000
- http_req_sending: p(99)=0.076, avg=0.035, min=0.007, med=0.038, max=0.306, p(90)=0.054, p(95)=0.058
- http_req_waiting: med=13.659, max=51.394, p(90)=27.281, p(95)=30.040, p(99)=46.558, avg=16.547, min=5.342
