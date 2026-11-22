# k6 summary

scenario: teacher_courses

- http_req_duration{expected_response:true}: avg=29.827, min=19.780, med=23.587, max=63.929, p(90)=41.916, p(95)=48.642, p(99)=63.317
- iterations: count=88.000, rate=8.663
- http_req_waiting: p(95)=48.532, p(99)=63.156, avg=29.732, min=19.735, med=23.491, max=63.726, p(90)=41.811
- http_req_failed: rate=0.000
- http_req_sending: min=0.007, med=0.042, max=0.092, p(90)=0.049, p(95)=0.055, p(99)=0.082, avg=0.042
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- vus: min=2.000, max=2.000
- http_req_duration: min=19.780, med=23.587, max=63.929, p(90)=41.916, p(95)=48.642, p(99)=63.317, avg=29.827
- http_req_connecting: med=0.000, max=0.083, p(90)=0.000, p(95)=0.000, p(99)=0.076, avg=0.002, min=0.000
- http_req_receiving: avg=0.053, min=0.017, med=0.046, max=0.158, p(90)=0.082, p(95)=0.109, p(99)=0.125
- http_req_blocked: min=0.001, med=0.012, max=0.113, p(90)=0.019, p(95)=0.035, p(99)=0.101, avg=0.015
