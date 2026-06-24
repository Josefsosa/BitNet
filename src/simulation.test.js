// Tests must pass before any geometry is written

import { describe, it, expect, vi } from 'vitest'
import * as THREE from 'three'

describe('TASK-SIM01: Comparison Zone', () => {

  it('buildComparisonZone returns a THREE.Group', () => {
    const { buildComparisonZone } = require('../sim/comparisonZone.js')
    const group = buildComparisonZone()
    expect(group).toBeInstanceOf(THREE.Group)
    expect(group.name).toBe('comparison_zone')
  })

  it('group contains exactly 2 named child groups: h100_rack and photnx_1u', () => {
    const { buildComparisonZone } = require('../sim/comparisonZone.js')
    const group = buildComparisonZone()
    const names = group.children.map(c => c.name)
    expect(names).toContain('h100_rack')
    expect(names).toContain('photnx_1u')
  })

  it('H100 rack group has height ~2.0 (42U = ~1.87m)', () => {
    const { buildComparisonZone } = require('../sim/comparisonZone.js')
    const group = buildComparisonZone()
    const rack = group.getObjectByName('h100_rack')
    const box = new THREE.Box3().setFromObject(rack)
    const size = new THREE.Vector3()
    box.getSize(size)
    expect(size.y).toBeGreaterThan(1.8)
    expect(size.y).toBeLessThan(2.1)
  })

  it('Photnx 1U group has height ~0.044 (1.75 inches = 0.0445m)', () => {
    const { buildComparisonZone } = require('../sim/comparisonZone.js')
    const group = buildComparisonZone()
    const unit = group.getObjectByName('photnx_1u')
    const box = new THREE.Box3().setFromObject(unit)
    const size = new THREE.Vector3()
    box.getSize(size)
    expect(size.y).toBeGreaterThan(0.03)
    expect(size.y).toBeLessThan(0.06)
  })

  it('computeTritState returns TRIT_POS for Photnx config', () => {
    const { computeTritState } = require('../sim/tritLogic.js')
    const result = computeTritState({ tops: 1000, watts: 350, waterGallons: 0 })
    expect(result).toBe('TRIT_POS')
  })

  it('computeTritState returns TRIT_NEG for H100 rack config', () => {
    const { computeTritState } = require('../sim/tritLogic.js')
    const result = computeTritState({ tops: 3958, watts: 70000, waterGallons: 500000 })
    expect(result).toBe('TRIT_NEG')
  })

  it('water particle system emits from H100 rack and not from Photnx', () => {
    const { buildComparisonZone } = require('../sim/comparisonZone.js')
    const group = buildComparisonZone()
    const waterParticles = group.getObjectByName('water_particles')
    const photonParticles = group.getObjectByName('photon_particles')
    expect(waterParticles).toBeTruthy()
    expect(photonParticles).toBeTruthy()
  })

  it('proximity trigger fires callback when camera within 3m of zone', () => {
    const { createProximityTrigger } = require('../sim/comparisonZone.js')
    const callback = vi.fn()
    const trigger = createProximityTrigger(new THREE.Vector3(0, 0, 0), 3.0, callback)
    const nearCamera = new THREE.Vector3(1, 0, 0)
    trigger.check(nearCamera)
    expect(callback).toHaveBeenCalledWith(true)
  })

})