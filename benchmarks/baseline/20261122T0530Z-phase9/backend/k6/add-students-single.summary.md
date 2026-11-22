# k6 summary

scenario: add_students

- http_req_duration: avg=18.282, min=18.282, med=18.282, max=18.282, p(90)=18.282, p(95)=18.282, p(99)=18.282
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: max=18.282, p(90)=18.282, p(95)=18.282, p(99)=18.282, avg=18.282, min=18.282, med=18.282
- http_req_connecting: p(95)=0.098, p(99)=0.098, avg=0.098, min=0.098, med=0.098, max=0.098, p(90)=0.098
- iterations: count=1.000, rate=4.553
- http_req_sending: avg=0.130, min=0.130, med=0.130, max=0.130, p(90)=0.130, p(95)=0.130, p(99)=0.130
- http_req_blocked: avg=0.147, min=0.147, med=0.147, max=0.147, p(90)=0.147, p(95)=0.147, p(99)=0.147
- http_req_waiting: max=18.104, p(90)=18.104, p(95)=18.104, p(99)=18.104, avg=18.104, min=18.104, med=18.104
- http_req_receiving: med=0.048, max=0.048, p(90)=0.048, p(95)=0.048, p(99)=0.048, avg=0.048, min=0.048
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
